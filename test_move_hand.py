import sys
from inspire_sdkpy import inspire_sdk, inspire_hand_defaut
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from inspire_sdkpy import inspire_dds
import time
import numpy as np

if __name__ == "__main__":
    print("=" * 50)
    print("Teste de Movimento - Mão DIREITA")
    print("IP: 192.168.123.211")
    print("=" * 50)

    # Inicia o driver (faz a ponte ModbusTCP <-> DDS)
    print("\n1️⃣ Conectando ao ModbusTCP...")
    handler = inspire_sdk.ModbusDataHandler(
        ip='192.168.123.211',
        LR='r',
        device_id=1
        # initDDS=True é o padrão, deixe o handler inicializar o DDS
    )
    time.sleep(1)
    print("✅ Driver conectado!\n")

    # Cria publisher para enviar comandos
    print("2️⃣ Criando publisher DDS...")
    pubr = ChannelPublisher("rt/inspire_hand/ctrl/r", inspire_dds.inspire_hand_ctrl)
    pubr.Init()
    time.sleep(0.5)
    print("✅ Publisher criado!\n")

    # Prepara comando
    cmd = inspire_hand_defaut.get_inspire_hand_ctrl()

    print("3️⃣ Iniciando sequência de movimentos...\n")

    try:
        # Movimento 1: Fechar todos os dedos
        print("🖐️  Fechando mão...")
        cmd.angle_set = [1000, 1000, 1000, 1000, 1000, 1000]
        cmd.mode = 0b0001  # Modo 1: controle por ângulo
        pubr.Write(cmd)
        time.sleep(2)

        # Movimento 2: Abrir todos os dedos
        print("✋  Abrindo mão...")
        cmd.angle_set = [0, 0, 0, 0, 0, 0]
        cmd.mode = 0b0001
        pubr.Write(cmd)
        time.sleep(2)

        # Movimento 3: Loop de abrir/fechar
        print("🔄  Iniciando loop (Ctrl+C para parar)...\n")
        angle = 0
        for i in range(100):
            angle = 1000 if angle == 0 else 0
            cmd.angle_set = [angle] * 6
            cmd.mode = 0b0001

            if pubr.Write(cmd):
                print(f"Iteração {i+1}: {'Fechando' if angle == 1000 else 'Abrindo'} | Ângulo: {angle}")
            else:
                print("⚠️  Aguardando subscriber...")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n✅ Programa finalizado")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
