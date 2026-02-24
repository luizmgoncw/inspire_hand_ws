import sys
from inspire_sdkpy import inspire_sdk, inspire_hand_defaut
import time

if __name__ == "__main__":
    print("=" * 50)
    print("Testando mão DIREITA")
    print("IP: 192.168.123.211")
    print("Tópico DDS: rt/inspire_hand/*/r")
    print("=" * 50)

    try:
        handler = inspire_sdk.ModbusDataHandler(
            ip='192.168.123.211',
            LR='r',
            device_id=1
        )
        time.sleep(0.5)

        print("\n✅ Conexão estabelecida!")
        print("Lendo dados da mão... (Ctrl+C para parar)\n")

        call_count = 0
        start_time = time.perf_counter()

        while True:
            data_dict = handler.read()
            call_count += 1
            time.sleep(0.001)

            if call_count % 100 == 0:
                elapsed_time = time.perf_counter() - start_time
                frequency = call_count / elapsed_time
                print(f"Frequência: {frequency:.2f} Hz | Chamadas: {call_count}")

    except KeyboardInterrupt:
        print("\n\n✅ Programa finalizado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
