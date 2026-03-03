#!/usr/bin/env python3
"""
Standalone PICO controller -> Redis publisher for testing Inspire hands.
No TWIST2 teleop, no MuJoCo, no retargeting. Just reads the PICO
controller buttons and publishes controller_data to Redis.

Usage:
  1. Open XRoboToolkit PC Service on Ubuntu
  2. On PICO: open XRoboToolkit Client, connect to PC IP, start streaming
  3. Run:  python test_hands_pico.py
  4. In another terminal:  bash inspire_hand.sh
  5. Press Index Trigger / Grip on PICO controllers to see hands react
"""

import json
import signal
import sys
import time

import xrobotoolkit_sdk as xrt
import redis

running = True
def sigint_handler(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, sigint_handler)

# Init
xrt.init()
r = redis.Redis(host="localhost", port=6379, db=0)
r.ping()

print("PICO -> Redis controller publisher")
print("=" * 50)
print("Waiting for PICO connection...")

# Wait for timestamp (means PICO is connected)
for i in range(100):
    if xrt.get_time_stamp_ns() != 0:
        print(f"PICO connected after {(i+1)*0.1:.1f}s")
        break
    time.sleep(0.1)
else:
    print("WARNING: No PICO timestamp after 10s, continuing anyway...")

print()
print("Publishing controller_data to Redis at 50 Hz.")
print("Press Ctrl+C to stop.\n")

while running:
    controller_data = {
        "LeftController": {
            "index_trig": xrt.get_left_trigger(),
            "grip": xrt.get_left_grip(),
            "key_one": xrt.get_X_button(),
            "key_two": xrt.get_Y_button(),
            "axis": xrt.get_left_axis(),
            "axis_click": xrt.get_left_axis_click(),
        },
        "RightController": {
            "index_trig": xrt.get_right_trigger(),
            "grip": xrt.get_right_grip(),
            "key_one": xrt.get_A_button(),
            "key_two": xrt.get_B_button(),
            "axis": xrt.get_right_axis(),
            "axis_click": xrt.get_right_axis_click(),
        },
        "timestamp": xrt.get_time_stamp_ns(),
    }

    r.set("controller_data", json.dumps(controller_data))

    # Show active buttons
    lt = controller_data["LeftController"]["index_trig"]
    lg = controller_data["LeftController"]["grip"]
    rt = controller_data["RightController"]["index_trig"]
    rg = controller_data["RightController"]["grip"]

    print(f"  L-trig={lt:.2f} L-grip={lg:.2f} | R-trig={rt:.2f} R-grip={rg:.2f}", flush=True)

    time.sleep(0.02)  # 50 Hz

xrt.close()
print("\nStopped.")
