import sys
import argparse
from inspire_sdkpy import inspire_sdk, inspire_hand_defaut
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from inspire_sdkpy import inspire_dds
import time

def parse_args():
    parser = argparse.ArgumentParser(description='Teste de movimento das maos com controle de velocidade')
    parser.add_argument('-s', '--speed', type=int, default=1000,
                        help='Velocidade dos dedos (0-1000, padrao: 1000 = maxima)')
    parser.add_argument('-i', '--iterations', type=int, default=100,
                        help='Numero de iteracoes do loop (padrao: 100)')
    parser.add_argument('-d', '--delay', type=float, default=1.0,
                        help='Delay entre movimentos em segundos (padrao: 1.0)')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # Limita velocidade entre 0 e 1000
    speed = max(0, min(1000, args.speed))

    print("=" * 50)
    print("Teste de Movimento - AMBAS AS MAOS (COM VELOCIDADE)")
    print("=" * 50)
    print(f"Velocidade: {speed}/1000")
    print(f"Iteracoes: {args.iterations}")
    print(f"Delay: {args.delay}s")
    print("Mao Esquerda: 192.168.123.210")
    print("Mao Direita:  192.168.123.211")
    print("=" * 50)

    # Inicializa o DDS
    print("\nInicializando DDS...")
    ChannelFactoryInitialize(0)
    time.sleep(0.5)
    print("DDS inicializado!\n")

    # Conecta as maos
    print("1. Conectando as maos...")

    print("   Conectando mao ESQUERDA (192.168.123.210)...")
    handler_left = inspire_sdk.ModbusDataHandler(
        ip='192.168.123.210',
        LR='l',
        device_id=1,
        initDDS=False
    )
    time.sleep(0.5)
    print("   Mao esquerda conectada!")

    print("   Conectando mao DIREITA (192.168.123.211)...")
    handler_right = inspire_sdk.ModbusDataHandler(
        ip='192.168.123.211',
        LR='r',
        device_id=1,
        initDDS=False
    )
    time.sleep(0.5)
    print("   Mao direita conectada!")

    print("Ambas as maos conectadas!\n")

    # Cria publishers
    print("2. Criando publishers DDS...")
    publ = ChannelPublisher("rt/inspire_hand/ctrl/l", inspire_dds.inspire_hand_ctrl)
    publ.Init()
    time.sleep(0.3)
    print("   Publisher esquerda criado!")

    pubr = ChannelPublisher("rt/inspire_hand/ctrl/r", inspire_dds.inspire_hand_ctrl)
    pubr.Init()
    time.sleep(0.3)
    print("   Publisher direita criado!")
    print("Publishers criados!\n")

    # Prepara comandos
    cmd_left = inspire_hand_defaut.get_inspire_hand_ctrl()
    cmd_right = inspire_hand_defaut.get_inspire_hand_ctrl()

    print("3. Iniciando sequencia de movimentos...\n")

    try:
        # Movimento 1: Fechar ambas as maos
        print("Fechando AMBAS as maos...")
        cmd_left.angle_set = [1000, 1000, 1000, 1000, 1000, 1000]
        cmd_left.speed_set = [speed] * 6
        cmd_left.mode = 0b1001  # Angulo + Velocidade

        cmd_right.angle_set = [1000, 1000, 1000, 1000, 1000, 1000]
        cmd_right.speed_set = [speed] * 6
        cmd_right.mode = 0b1001

        publ.Write(cmd_left)
        pubr.Write(cmd_right)
        time.sleep(2)

        # Movimento 2: Abrir ambas as maos
        print("Abrindo AMBAS as maos...")
        cmd_left.angle_set = [0, 0, 0, 0, 0, 0]
        cmd_left.speed_set = [speed] * 6
        cmd_left.mode = 0b1001

        cmd_right.angle_set = [0, 0, 0, 0, 0, 0]
        cmd_right.speed_set = [speed] * 6
        cmd_right.mode = 0b1001

        publ.Write(cmd_left)
        pubr.Write(cmd_right)
        time.sleep(2)

        # Loop de abrir/fechar
        print(f"Iniciando loop sincronizado (Ctrl+C para parar)...\n")
        angle = 0
        for i in range(args.iterations):
            angle = 1000 if angle == 0 else 0

            cmd_left.angle_set = [angle] * 6
            cmd_left.speed_set = [speed] * 6
            cmd_left.mode = 0b1001

            cmd_right.angle_set = [angle] * 6
            cmd_right.speed_set = [speed] * 6
            cmd_right.mode = 0b1001

            left_ok = publ.Write(cmd_left)
            right_ok = pubr.Write(cmd_right)

            if left_ok and right_ok:
                action = 'Fechando' if angle == 1000 else 'Abrindo'
                print(f"Iteracao {i+1}: {action} AMBAS | Angulo: {angle} | Velocidade: {speed}")
            else:
                if not left_ok:
                    print("Aguardando subscriber esquerda...")
                if not right_ok:
                    print("Aguardando subscriber direita...")

            time.sleep(args.delay)

    except KeyboardInterrupt:
        print("\n\nPrograma finalizado")
    except Exception as e:
        print(f"\nErro: {e}")
        import traceback
        traceback.print_exc()
