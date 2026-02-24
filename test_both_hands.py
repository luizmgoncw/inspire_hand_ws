import sys
from inspire_sdkpy import inspire_sdk, inspire_hand_defaut
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from inspire_sdkpy import inspire_dds
import time
import numpy as np

if __name__ == "__main__":
    print("=" * 50)
    print("Teste de Movimento - AMBAS AS MÃOS")
    print("Mão Esquerda: 192.168.123.210")
    print("Mão Direita:  192.168.123.211")
    print("=" * 50)

    # Inicializa o DDS uma única vez ANTES de criar os handlers
    print("\n🔧 Inicializando DDS...")
    ChannelFactoryInitialize(0)
    time.sleep(0.5)
    print("✅ DDS inicializado!\n")

    # Inicia os drivers (faz a ponte ModbusTCP <-> DDS)
    print("1️⃣ Conectando às mãos...")

    print("   Conectando mão ESQUERDA (192.168.123.210)...")
    handler_left = inspire_sdk.ModbusDataHandler(
        ip='192.168.123.210',
        LR='l',
        device_id=1,
        initDDS=False  # NÃO inicializa DDS (já foi inicializado acima)
    )
    time.sleep(0.5)
    print("   ✅ Mão esquerda conectada!")

    print("   Conectando mão DIREITA (192.168.123.211)...")
    handler_right = inspire_sdk.ModbusDataHandler(
        ip='192.168.123.211',
        LR='r',
        device_id=1,
        initDDS=False  # NÃO inicializa DDS (já foi inicializado acima)
    )
    time.sleep(0.5)
    print("   ✅ Mão direita conectada!")

    print("✅ Ambas as mãos conectadas!\n")

    # Cria publishers para enviar comandos
    print("2️⃣ Criando publishers DDS...")
    publ = ChannelPublisher("rt/inspire_hand/ctrl/l", inspire_dds.inspire_hand_ctrl)
    publ.Init()
    time.sleep(0.3)
    print("   ✅ Publisher esquerda criado!")

    pubr = ChannelPublisher("rt/inspire_hand/ctrl/r", inspire_dds.inspire_hand_ctrl)
    pubr.Init()
    time.sleep(0.3)
    print("   ✅ Publisher direita criado!")
    print("✅ Publishers criados!\n")

    # Prepara comandos
    cmd_left = inspire_hand_defaut.get_inspire_hand_ctrl()
    cmd_right = inspire_hand_defaut.get_inspire_hand_ctrl()

    print("3️⃣ Iniciando sequência de movimentos...\n")

    try:
        # Movimento 1: Fechar ambas as mãos
        print("🖐️🖐️  Fechando AMBAS as mãos...")
        cmd_left.angle_set = [1000, 1000, 1000, 1000, 1000, 1000]
        cmd_left.mode = 0b0001  # Modo 1: controle por ângulo
        cmd_right.angle_set = [1000, 1000, 1000, 1000, 1000, 1000]
        cmd_right.mode = 0b0001

        publ.Write(cmd_left)
        pubr.Write(cmd_right)
        time.sleep(2)

        # Movimento 2: Abrir ambas as mãos
        print("✋✋  Abrindo AMBAS as mãos...")
        cmd_left.angle_set = [0, 0, 0, 0, 0, 0]
        cmd_left.mode = 0b0001
        cmd_right.angle_set = [0, 0, 0, 0, 0, 0]
        cmd_right.mode = 0b0001

        publ.Write(cmd_left)
        pubr.Write(cmd_right)
        time.sleep(2)

        # Movimento 3: Loop de abrir/fechar sincronizado
        print("🔄  Iniciando loop sincronizado (Ctrl+C para parar)...\n")
        angle = 0
        for i in range(100):
            angle = 1000 if angle == 0 else 0

            cmd_left.angle_set = [angle] * 6
            cmd_left.mode = 0b0001
            cmd_right.angle_set = [angle] * 6
            cmd_right.mode = 0b0001

            left_ok = publ.Write(cmd_left)
            right_ok = pubr.Write(cmd_right)

            if left_ok and right_ok:
                action = 'Fechando' if angle == 1000 else 'Abrindo'
                print(f"Iteração {i+1}: {action} AMBAS | Ângulo: {angle}")
            else:
                if not left_ok:
                    print("⚠️  Aguardando subscriber esquerda...")
                if not right_ok:
                    print("⚠️  Aguardando subscriber direita...")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n✅ Programa finalizado")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
