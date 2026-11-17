import json
import urllib.request
import urllib.error

import paho.mqtt.client as mqtt

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from dotenv import load_dotenv

# Загрузка настроек HTTP-моста из gateway/.env
load_dotenv(Path(__file__).with_name(".env"))

GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN")
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765

# =====================================================
# 1. НАСТРОЙКИ MQTT
# =====================================================

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883

MQTT_TOPIC = "vineyard-smart/demo-esp32-8f31a2/telemetry"

# Темы удалённого управления
MQTT_TOPIC_COMMAND = "vineyard-smart/demo-esp32-8f31a2/command"
MQTT_TOPIC_ACK = "vineyard-smart/demo-esp32-8f31a2/ack"

CLIENT_ID = "vineyard-gateway-esp32-8f31a2-pc1"

# =====================================================
# НАСТРОЙКИ FASTAPI
# =====================================================

API_URL = "http://127.0.0.1:8000/api/v1/telemetry"
API_TIMEOUT = 5

# =====================================================
# ОТПРАВКА ТЕЛЕМЕТРИИ В FASTAPI
# =====================================================

def send_telemetry_to_api(payload: str) -> None:
    """Передаёт полученную телеметрию в FastAPI."""

    request = urllib.request.Request(
        API_URL,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=API_TIMEOUT,
        ) as response:

            print(
                f"[API] Данные сохранены. "
                f"HTTP {response.status}"
            )

    except urllib.error.HTTPError as error:
        print(f"[API] Ошибка HTTP: {error.code}")
        print(error.read().decode("utf-8", errors="replace"))

    except (urllib.error.URLError, TimeoutError) as error:
        print(f"[API] Не удалось отправить данные: {error}")

# =====================================================
# ОТПРАВКА КОМАНД ESP32
# =====================================================

def send_command(client, mode: str) -> bool:
    """Отправляет ESP32 команду переключения режима."""

    if mode not in ("AUTO", "MANUAL"):
        print(f"[GATEWAY] Недопустимый режим: {mode}")
        return False

    payload = json.dumps({"mode": mode})

    result = client.publish(
        MQTT_TOPIC_COMMAND,
        payload
    )

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"[MQTT] Команда отправлена: {mode}")
        return True

    print(f"[MQTT] Ошибка отправки команды. Код: {result.rc}")
    return False


# =====================================================
# HTTP-МОСТ ДЛЯ УПРАВЛЕНИЯ ESP32
# =====================================================

class CommandHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/command":
            self.send_error(404)
            return

        import hmac

        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {GATEWAY_TOKEN or ''}"

        if not GATEWAY_TOKEN or not hmac.compare_digest(auth, expected):
            self.send_error(401)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1024:
                self.send_error(400)
                return

            data = json.loads(self.rfile.read(length))
            mode = data.get("mode") if isinstance(data, dict) else None

            if mode not in ("AUTO", "MANUAL"):
                self.send_error(400)
                return

            if not send_command(self.server.mqtt_client, mode):
                self.send_error(502)
                return

            response = json.dumps({
                "status": "accepted",
                "mode": mode
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except (ValueError, json.JSONDecodeError):
            self.send_error(400)

    def log_message(self, format, *args):
        print("[HTTP]", format % args)


def run_http_server(mqtt_client):
    server = HTTPServer((HTTP_HOST, HTTP_PORT), CommandHandler)
    server.mqtt_client = mqtt_client

    print(f"[HTTP] Сервер управления запущен: http://{HTTP_HOST}:{HTTP_PORT}")

    server.serve_forever()


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
        client.subscribe(MQTT_TOPIC_ACK)

        print(f"[MQTT] Подписка: {MQTT_TOPIC}")
        print(f"[MQTT] Подписка: {MQTT_TOPIC_ACK}")

    else:
        print(f"[MQTT] Ошибка подключения. Код: {reason_code}")


def on_message(client, userdata, message):
    """Обрабатывает входящие MQTT-сообщения."""

    payload = message.payload.decode("utf-8", errors="replace")

    # Получено подтверждение команды от ESP32
    if message.topic == MQTT_TOPIC_ACK:

        print("\n[MQTT] Получено подтверждение от ESP32:")
        print(payload)

        try:
            ack = json.loads(payload)
            print(f"[MQTT] Статус: {ack.get('status')}")
            print(f"[MQTT] Режим: {ack.get('mode', 'не указан')}")

        except json.JSONDecodeError:
            print("[MQTT] Ошибка разбора ACK.")

        return

    # Получена телеметрия
    if message.topic == MQTT_TOPIC:

        print("\n[MQTT] Получено новое сообщение.")

        process_telemetry(payload)

        send_telemetry_to_api(payload)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Вызывается при отключении от брокера."""

    print(f"[MQTT] Соединение закрыто. Код: {reason_code}")


# =====================================================
# 4. ЗАПУСК PYTHON GATEWAY
# =====================================================

def main():

    if not GATEWAY_TOKEN:
        raise RuntimeError(
            "Не задан GATEWAY_TOKEN в файле gateway/.env"
        )

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
    print("Ожидание телеметрии от ESP32...\\n")

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

        http_thread = threading.Thread(
            target=run_http_server,
            args=(client,),
            daemon=True
        )
        http_thread.start()

        client.loop_forever()

    except KeyboardInterrupt:
        print("\\n[GATEWAY] Остановка по команде пользователя.")

    except OSError as error:
        print(f"[GATEWAY] Ошибка соединения или HTTP-сервера: {error}")

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
