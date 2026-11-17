import json
import paho.mqtt.client as mqtt


# =====================================================
# 1. НАСТРОЙКИ MQTT
# =====================================================

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883

MQTT_TOPIC = "vineyard-smart/demo-esp32-8f31a2/telemetry"

CLIENT_ID = "vineyard-python-gateway"


# =====================================================
# 2. ОБРАБОТКА ПОЛУЧЕННОЙ ТЕЛЕМЕТРИИ
# =====================================================

def process_telemetry(payload: str) -> None:
    """Разбирает JSON и выводит показания виноградника."""

    try:
        data = json.loads(payload)

        zone1 = data["zone1"]
        zone2 = data["zone2"]
        air = data["air"]

        print("\n" + "=" * 55)
        print("       МОНИТОРИНГ ВИНОГРАДНИКА — PYTHON GATEWAY")
        print("=" * 55)

        print(f"Устройство: {data.get('device', 'неизвестно')}")
        print(f"Режим управления: {data.get('mode', 'неизвестно')}")

        print("\nЗОНА 1")
        print(f"Влажность почвы: {zone1.get('soil')} %")
        print(f"Значение ADC: {zone1.get('soil_adc')}")
        print(f"Полив: {'ВКЛ' if zone1.get('irrigation') else 'ВЫКЛ'}")
        print(f"Датчик исправен: {zone1.get('sensor_valid')}")

        print("\nЗОНА 2")
        print(f"Влажность почвы: {zone2.get('soil')} %")
        print(f"Значение ADC: {zone2.get('soil_adc')}")
        print(f"Полив: {'ВКЛ' if zone2.get('irrigation') else 'ВЫКЛ'}")
        print(f"Датчик исправен: {zone2.get('sensor_valid')}")

        print("\nАТМОСФЕРНЫЕ ДАННЫЕ")
        print(f"Температура: {air.get('temperature')} °C")
        print(f"Влажность воздуха: {air.get('humidity')} %")
        print(f"Данные датчика DHT: {air.get('valid')}")

        print("\nДОПОЛНИТЕЛЬНЫЕ ДАТЧИКИ")
        print(f"Освещённость (ADC): {data.get('light_adc')}")
        print(f"Дождь (ADC): {data.get('rain_adc')}")
        print(f"Дождь обнаружен: {'ДА' if data.get('raining') else 'НЕТ'}")

        print("=" * 55)

    except (json.JSONDecodeError, KeyError, TypeError) as error:
        print(f"[GATEWAY] Ошибка обработки сообщения: {error}")
        print(f"[GATEWAY] Полученные данные: {payload}")


# =====================================================
# 3. СОБЫТИЯ MQTT
# =====================================================

def on_connect(client, userdata, flags, reason_code, properties):
    """Вызывается после подключения к MQTT-брокеру."""

    if reason_code == 0:
        print("[MQTT] Подключение к брокеру успешно.")

        client.subscribe(MQTT_TOPIC)

        print(f"[MQTT] Подписка: {MQTT_TOPIC}")

    else:
        print(f"[MQTT] Ошибка подключения. Код: {reason_code}")


def on_message(client, userdata, message):
    """Вызывается при получении сообщения."""

    payload = message.payload.decode("utf-8", errors="replace")

    print("\n[MQTT] Получено новое сообщение.")

    process_telemetry(payload)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Вызывается при отключении от брокера."""

    print(f"[MQTT] Соединение закрыто. Код: {reason_code}")


# =====================================================
# 4. ЗАПУСК PYTHON GATEWAY
# =====================================================

def main():

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    print("==============================================")
    print("       VINEYARD SMART — PYTHON GATEWAY")
    print("==============================================")
    print(f"Брокер: {MQTT_BROKER}:{MQTT_PORT}")
    print("Ожидание телеметрии от ESP32...\n")

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()

    except KeyboardInterrupt:
        print("\n[GATEWAY] Остановка по команде пользователя.")

    except OSError as error:
        print(f"[GATEWAY] Ошибка соединения: {error}")

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
