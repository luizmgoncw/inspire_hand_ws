#!/usr/bin/env python3
"""
TWIST2 -> Inspire Hand Bridge
=============================
Reads controller_data from Redis (published by TWIST2 teleop) and publishes
DDS commands to control the Inspire dexterous hands.

Architecture:
  PICO Controller -> TWIST2 teleop -> Redis (controller_data)
       -> [this bridge] -> DDS topics -> Headless Driver -> Modbus TCP -> Inspire Hands

Button mapping (same as TWIST2):
  - Index Trigger (left/right): Close hand (gradual, 0->1)
  - Grip button  (left/right): Open hand  (gradual, 1->0)

Setup (one-time, in gmr venv):
  source ~/Documents/TWIST2/venvs/gmr/bin/activate
  pip install cyclonedds==0.10.2   # if not already installed

Launch order:
  Terminal 1 - Inspire Headless drivers (DDS <-> Modbus TCP <-> hardware):
    source ~/Documents/TWIST2/venvs/gmr/bin/activate
    cd ~/Documents/Unitree/inspire_hand_ws/inspire_hand_sdk/example
    python Headless_driver_double.py

  Terminal 2 - TWIST2 teleop (publishes controller_data to Redis):
    source ~/Documents/TWIST2/venvs/gmr/bin/activate
    cd ~/Documents/TWIST2/TWIST2/deploy_real
    python xrobot_teleop_to_robot_w_hand.py --robot unitree_g1

  Terminal 3 - This bridge (Redis -> DDS):
    source ~/Documents/TWIST2/venvs/gmr/bin/activate
    cd ~/Documents/Unitree/inspire_hand_ws
    python twist2_inspire_bridge.py [--redis_ip localhost] [--speed 500]
"""

import argparse
import gc
import json
import os
import signal
import sys
import threading
import time

# Auto-add SDK paths when running from inspire_hand_ws directory
_script_dir = os.path.dirname(os.path.abspath(__file__))
for _subdir in ("inspire_hand_sdk", "unitree_sdk2_python"):
    _sdk_path = os.path.join(_script_dir, _subdir)
    if os.path.isdir(_sdk_path) and _sdk_path not in sys.path:
        sys.path.insert(0, _sdk_path)

import importlib.util  # noqa: E402
import redis  # noqa: E402
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize  # noqa: E402

# Load Inspire DDS types WITHOUT triggering inspire_sdkpy/__init__.py
# (which unconditionally imports pymodbus, PyQt5, etc. for the GUI/driver).
# We only need the DDS message dataclass and a factory function.
_inspire_sdk_root = os.path.join(_script_dir, "inspire_hand_sdk", "inspire_sdkpy")


def _load_module_from_file(name, filepath):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 1) Load the CycloneDDS dataclass  (inspire_hand_ctrl)
_dds_ctrl_mod = _load_module_from_file(
    "inspire_hand_ctrl_mod",
    os.path.join(_inspire_sdk_root, "inspire_dds", "_inspire_hand_ctrl.py"),
)
inspire_hand_ctrl = _dds_ctrl_mod.inspire_hand_ctrl


class InspireHandBridge:
    """Bridge between TWIST2 Redis controller data and Inspire hand DDS control."""

    def __init__(self, redis_ip="localhost", redis_port=6379, speed=500,
                 movement_step=0.05, loop_hz=50):
        self.loop_hz = loop_hz
        self.movement_step = movement_step
        self.speed = speed

        # Hand state: 0.0 = fully open, 1.0 = fully closed
        self.hand_left_position = 0.0
        self.hand_right_position = 0.0

        # --- Redis ---
        print(f"[Bridge] Connecting to Redis at {redis_ip}:{redis_port}...")
        self.redis_client = redis.Redis(host=redis_ip, port=redis_port, db=0)
        self.redis_client.ping()
        print("[Bridge] Redis connected.")

        # --- DDS ---
        ChannelFactoryInitialize(0)

        self.pub_left = ChannelPublisher("rt/inspire_hand/ctrl/l",
                                         inspire_hand_ctrl)
        self.pub_left.Init()

        self.pub_right = ChannelPublisher("rt/inspire_hand/ctrl/r",
                                          inspire_hand_ctrl)
        self.pub_right.Init()
        print("[Bridge] DDS publishers initialized (ctrl/l, ctrl/r).")

        # Pre-allocate DDS command objects (avoids GC pressure from 100 allocs/s)
        self._cmd_left = inspire_hand_ctrl(
            pos_set=[0] * 6, angle_set=[0] * 6,
            force_set=[0] * 6, speed_set=[self.speed] * 6, mode=0b1001,
        )
        self._cmd_right = inspire_hand_ctrl(
            pos_set=[0] * 6, angle_set=[0] * 6,
            force_set=[0] * 6, speed_set=[self.speed] * 6, mode=0b1001,
        )

        # Graceful shutdown
        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        print("\n[Bridge] Shutdown requested, opening hands...", flush=True)
        self._running = False

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _read_controller_data(self):
        """Read the latest controller_data JSON from Redis."""
        raw = self.redis_client.get("controller_data")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def _update_hand_state(self, controller_data):
        """Update internal hand positions based on controller analog inputs.

        Mirrors the logic in TWIST2's StateMachine.update():
          - index_trig  → close (position increases)
          - grip        → open  (position decreases)

        The trigger/grip values are analog floats [0.0, 1.0], so we scale
        the movement step proportionally: light press = slow, full press = fast.
        A deadzone filters out accidental touches and controller noise.
        """
        if controller_data is None:
            return

        deadzone = 0.02

        # Right hand
        right = controller_data.get("RightController", {})
        r_trig = float(right.get("index_trig", 0.0))
        r_grip = float(right.get("grip", 0.0))
        if r_trig > deadzone:
            self.hand_right_position = min(1.0, self.hand_right_position + self.movement_step * r_trig ** 2)
        elif r_grip > deadzone:
            self.hand_right_position = max(0.0, self.hand_right_position - self.movement_step * r_grip ** 2)

        # Left hand
        left = controller_data.get("LeftController", {})
        l_trig = float(left.get("index_trig", 0.0))
        l_grip = float(left.get("grip", 0.0))
        if l_trig > deadzone:
            self.hand_left_position = min(1.0, self.hand_left_position + self.movement_step * l_trig ** 2)
        elif l_grip > deadzone:
            self.hand_left_position = max(0.0, self.hand_left_position - self.movement_step * l_grip ** 2)

    def _position_to_angle(self, position):
        """Convert normalised position [0.0, 1.0] to Inspire angle [0, 1000]."""
        return int(round(position * 1000))

    def _publish_hand_command(self, publisher, cmd, position):
        """Update pre-allocated command and publish."""
        angle = self._position_to_angle(position)
        cmd.angle_set = [angle] * 6
        publisher.Write(cmd)

    def _open_hands(self):
        """Send open command to both hands (safety/shutdown)."""
        self._cmd_left.angle_set = [0] * 6
        self._cmd_right.angle_set = [0] * 6
        self.pub_left.Write(self._cmd_left)
        self.pub_right.Write(self._cmd_right)

    # ------------------------------------------------------------------
    # DDS publisher thread
    # ------------------------------------------------------------------

    def _dds_loop(self):
        """Publishes hand commands over DDS at a steady rate, independent of main loop."""
        period = 1.0 / self.loop_hz
        while self._running:
            t0 = time.monotonic()
            self._publish_hand_command(self.pub_left, self._cmd_left, self.hand_left_position)
            self._publish_hand_command(self.pub_right, self._cmd_right, self.hand_right_position)
            elapsed = time.monotonic() - t0
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ------------------------------------------------------------------
    # Main loop (Redis read + state update + print only)
    # ------------------------------------------------------------------

    def run(self):
        print(f"[Bridge] Running at {self.loop_hz} Hz  |  step={self.movement_step}  |  speed={self.speed}")
        print("[Bridge] Waiting for controller_data on Redis...")
        print("[Bridge] Controls: index_trig = CLOSE hand  |  grip = OPEN hand")

        # Start DDS publisher in a separate thread (decoupled from Redis/print)
        dds_thread = threading.Thread(target=self._dds_loop, daemon=True)
        dds_thread.start()

        # Disable GC during the loop to prevent micro-pauses
        gc.disable()

        period = 1.0 / self.loop_hz
        prev_left = -1.0
        prev_right = -1.0
        got_first_data = False
        gc_counter = 0

        try:
            while self._running:
                t0 = time.monotonic()

                controller_data = self._read_controller_data()

                if controller_data is not None and not got_first_data:
                    print("[Bridge] Receiving controller data from Redis!", flush=True)
                    got_first_data = True

                self._update_hand_state(controller_data)

                # Print when the position actually changes (avoid terminal spam)
                if (self.hand_left_position != prev_left
                        or self.hand_right_position != prev_right):
                    prev_left = self.hand_left_position
                    prev_right = self.hand_right_position
                    l_angle = self._position_to_angle(self.hand_left_position)
                    r_angle = self._position_to_angle(self.hand_right_position)
                    l_bar = "#" * int(self.hand_left_position * 20)
                    r_bar = "#" * int(self.hand_right_position * 20)
                    print(
                        f"  L: {l_angle:4d}/1000 [{l_bar:<20s}]  |  "
                        f"R: {r_angle:4d}/1000 [{r_bar:<20s}]",
                        flush=True,
                    )

                # Manual GC every ~2 seconds instead of random pauses
                gc_counter += 1
                if gc_counter >= self.loop_hz * 2:
                    gc.collect()
                    gc_counter = 0

                # Rate limiting
                elapsed = time.monotonic() - t0
                sleep_time = period - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            gc.enable()

        # Shutdown: open hands for safety
        self._open_hands()
        print("[Bridge] Hands opened. Goodbye.")


def parse_args():
    p = argparse.ArgumentParser(description="TWIST2 → Inspire Hand DDS bridge")
    p.add_argument("--redis_ip", type=str, default="localhost",
                   help="Redis server IP (default: localhost)")
    p.add_argument("--redis_port", type=int, default=6379,
                   help="Redis server port (default: 6379)")
    p.add_argument("--speed", type=int, default=500,
                   help="Inspire hand speed 0-1000 (default: 500)")
    p.add_argument("--step", type=float, default=0.02,
                   help="Hand position step per tick (default: 0.02 = 2%%)")
    p.add_argument("--hz", type=int, default=50,
                   help="Loop frequency in Hz (default: 50)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    bridge = InspireHandBridge(
        redis_ip=args.redis_ip,
        redis_port=args.redis_port,
        speed=args.speed,
        movement_step=args.step,
        loop_hz=args.hz,
    )
    bridge.run()
