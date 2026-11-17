
#include <Arduino.h>
#include <DHT.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <math.h>

// =====================================================
// 1. НАСТРОЙКА GPIO ESP32
// =====================================================

const int PIN_SOIL_1 = 34;
const int PIN_SOIL_2 = 35;

const int PIN_LDR = 32;
const int PIN_DHT = 4;
const int PIN_RAIN = 33;

const int PIN_RELAY_1 = 25;
const int PIN_RELAY_2 = 26;

const int PIN_LED_1 = 18;
const int PIN_LED_2 = 19;

const int PIN_MODE_SWITCH = 27;

const int PIN_BUTTON_1 = 14;
const int PIN_BUTTON_2 = 13;


// =====================================================
// 2. ПАРАМЕТРЫ СИСТЕМЫ
// =====================================================

const float HUMIDITY_START = 35.0;
const float HUMIDITY_STOP = 60.0;

const unsigned long MAX_WATERING_MS = 15000;
const unsigned long LOOP_INTERVAL = 2000;
const unsigned long DEBOUNCE_MS = 50;


// Калибровка датчиков для модели Wokwi

const int SOIL_DRY_RAW = 0;
const int SOIL_WET_RAW = 4095;

const int RAIN_THRESHOLD = 1000;


// =====================================================
// 3. НАСТРОЙКИ WI-FI
// =====================================================

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";


// =====================================================
// 4. НАСТРОЙКИ MQTT
// =====================================================

const char* MQTT_SERVER = "test.mosquitto.org";
const int MQTT_PORT = 1883;


// Учебное пространство проекта.
// Для отдельного проекта можно изменить суффикс.

const char* MQTT_BASE_TOPIC =
  "vineyard-smart/demo-esp32-8f31a2";

const char* MQTT_TOPIC_TELEMETRY =
  "vineyard-smart/demo-esp32-8f31a2/telemetry";

const char* MQTT_TOPIC_STATUS =
  "vineyard-smart/demo-esp32-8f31a2/status";


const unsigned long WIFI_RETRY_INTERVAL = 10000;
const unsigned long MQTT_RETRY_INTERVAL = 5000;


// =====================================================
// 5. СЕТЕВЫЕ ОБЪЕКТЫ
// =====================================================

WiFiClient espClient;

PubSubClient mqttClient(espClient);


// Время последних попыток подключения

unsigned long lastWiFiAttempt = 0;
unsigned long lastMqttAttempt = 0;


// Флаг первого подключения

bool wifiWasConnected = false;
bool mqttWasConnected = false;


// =====================================================
// 6. ДАТЧИК DHT22
// =====================================================

DHT dht(PIN_DHT, DHT22);


// =====================================================
// 7. СТРУКТУРА ДАННЫХ ДАТЧИКОВ
// =====================================================

struct SensorData {

  float soil1;
  float soil2;

  int soil1Raw;
  int soil2Raw;

  float airTemp;
  float airHum;

  int lightRaw;
  int rainRaw;

  bool soil1Valid;
  bool soil2Valid;
  bool airValid;
};


// =====================================================
// 8. СБОР ДАННЫХ С ДАТЧИКОВ
// =====================================================

class SensorManager {

public:

  void begin() {

    dht.begin();

    pinMode(PIN_SOIL_1, INPUT);
    pinMode(PIN_SOIL_2, INPUT);
    pinMode(PIN_LDR, INPUT);
    pinMode(PIN_RAIN, INPUT);
  }


  float calibrateSoil(int rawValue) {

    if (SOIL_DRY_RAW == SOIL_WET_RAW) {
      return 0.0;
    }

    float humidity =
      (float)(rawValue - SOIL_DRY_RAW) /
      (SOIL_WET_RAW - SOIL_DRY_RAW) * 100.0;

    return constrain(humidity, 0.0, 100.0);
  }


  SensorData readAll() {

    SensorData data = {};

    data.soil1Raw = analogRead(PIN_SOIL_1);
    data.soil2Raw = analogRead(PIN_SOIL_2);

    data.soil1Valid =
      data.soil1Raw >= 0 &&
      data.soil1Raw <= 4095;

    data.soil2Valid =
      data.soil2Raw >= 0 &&
      data.soil2Raw <= 4095;

    data.soil1 = calibrateSoil(data.soil1Raw);
    data.soil2 = calibrateSoil(data.soil2Raw);

    data.lightRaw = analogRead(PIN_LDR);
    data.rainRaw = analogRead(PIN_RAIN);

    data.airTemp = dht.readTemperature();
    data.airHum = dht.readHumidity();

    data.airValid =
      !isnan(data.airTemp) &&
      !isnan(data.airHum);

    return data;
  }
};


// =====================================================
// 9. ОБРАБОТКА И ПРОВЕРКА ДАННЫХ
// =====================================================

class DataProcessor {

public:

  bool validateSoil(float humidity) {

    return
      !isnan(humidity) &&
      humidity >= 0.0 &&
      humidity <= 100.0;
  }


  bool validateAir(SensorData &data) {

    return
      data.airValid &&
      data.airTemp >= -40.0 &&
      data.airTemp <= 80.0 &&
      data.airHum >= 0.0 &&
      data.airHum <= 100.0;
  }


  String analyzeLight(int lightRaw) {

    if (lightRaw < 1000) {
      return "Низкая освещенность";
    }

    else if (lightRaw < 2800) {
      return "Умеренная освещенность";
    }

    else {
      return "Высокая освещенность";
    }
  }


  bool isRaining(int rainRaw) {

    return rainRaw >= RAIN_THRESHOLD;
  }


  String analyzeRain(int rainRaw) {

    if (rainRaw < RAIN_THRESHOLD) {
      return "Дождя нет";
    }

    else if (rainRaw < 2500) {
      return "Небольшие осадки";
    }

    else {
      return "Сильные осадки";
    }
  }
};


// =====================================================
// 10. УПРАВЛЕНИЕ РЕЛЕ И ИНДИКАЦИЕЙ
// =====================================================

class RelayManager {

private:

  int relayPin;
  int ledPin;

  bool state;


public:

  RelayManager(int rPin, int lPin)
    : relayPin(rPin),
      ledPin(lPin),
      state(false) {}


  void begin() {

    pinMode(relayPin, OUTPUT);
    pinMode(ledPin, OUTPUT);

    setState(false);
  }


  void setState(bool active) {

    state = active;

    digitalWrite(relayPin, state ? HIGH : LOW);
    digitalWrite(ledPin, state ? HIGH : LOW);
  }


  bool getState() {

    return state;
  }
};


// =====================================================
// 11. КОНТРОЛЛЕР ПОЛИВА
// =====================================================

class IrrigationController {

private:

  RelayManager &actuator;

  unsigned long startTime;

  bool safetyLockout;
  bool manualRequest;

  bool previousMode;
  bool modeInitialized;

  String zoneName;


public:

  IrrigationController(
    RelayManager &rel,
    String name
  )
    : actuator(rel),
      startTime(0),
      safetyLockout(false),
      manualRequest(false),
      previousMode(false),
      modeInitialized(false),
      zoneName(name) {}


  void toggleManualRequest() {

    manualRequest = !manualRequest;
  }


  void clearManualRequest() {

    manualRequest = false;
  }


  void update(
    float soilMoisture,
    bool sensorOk,
    bool raining,
    bool manualMode,
    unsigned long now
  ) {

    // Обнаружение переключения режима

    if (
      !modeInitialized ||
      manualMode != previousMode
    ) {

      if (actuator.getState()) {
        actuator.setState(false);
      }

      manualRequest = false;

      previousMode = manualMode;
      modeInitialized = true;

      Serial.println(
        "[" + zoneName + "] Режим управления изменен."
      );
    }


    // Контроль максимального времени полива

    if (
      actuator.getState() &&
      now - startTime >= MAX_WATERING_MS
    ) {

      actuator.setState(false);

      manualRequest = false;
      safetyLockout = true;

      Serial.println(
        "[" + zoneName +
        "] АВАРИЯ: превышено время полива!"
      );

      return;
    }


    // Проверка датчика почвы

    if (!sensorOk) {

      if (actuator.getState()) {
        actuator.setState(false);
      }

      manualRequest = false;

      Serial.println(
        "[" + zoneName +
        "] Ошибка датчика почвы. Полив остановлен."
      );

      return;
    }


    // Защита от дождя

    if (raining) {

      if (actuator.getState()) {

        actuator.setState(false);

        Serial.println(
          "[" + zoneName +
          "] Полив остановлен: дождь."
        );
      }

      manualRequest = false;

      return;
    }


    // Снятие аварийной блокировки

    if (
      safetyLockout &&
      soilMoisture > HUMIDITY_STOP
    ) {

      safetyLockout = false;

      Serial.println(
        "[" + zoneName +
        "] Блокировка снята."
      );
    }


    if (safetyLockout) {
      return;
    }


    // РУЧНОЙ РЕЖИМ

    if (manualMode) {

      if (
        manualRequest &&
        !actuator.getState()
      ) {

        actuator.setState(true);

        startTime = now;

        Serial.println(
          "[" + zoneName +
          "] Ручной запуск полива."
        );
      }

      else if (
        !manualRequest &&
        actuator.getState()
      ) {

        actuator.setState(false);

        Serial.println(
          "[" + zoneName +
          "] Ручная остановка полива."
        );
      }

      return;
    }


    // АВТОМАТИЧЕСКИЙ РЕЖИМ

    manualRequest = false;


    if (
      soilMoisture < HUMIDITY_START &&
      !actuator.getState()
    ) {

      actuator.setState(true);

      startTime = now;

      Serial.println(
        "[" + zoneName +
        "] Автоматический запуск полива."
      );
    }


    else if (
      soilMoisture > HUMIDITY_STOP &&
      actuator.getState()
    ) {

      actuator.setState(false);

      Serial.println(
        "[" + zoneName +
        "] Автоматическая остановка полива."
      );
    }
  }
};


// =====================================================
// 12. ОБРАБОТКА КНОПОК
// =====================================================

struct ButtonInput {

  int pin;

  bool lastReading;
  bool stableState;

  unsigned long lastChange;
};


ButtonInput button1;
ButtonInput button2;


void beginButton(ButtonInput &button, int pin) {

  button.pin = pin;

  pinMode(pin, INPUT_PULLUP);

  bool initialState = digitalRead(pin);

  button.lastReading = initialState;
  button.stableState = initialState;

  button.lastChange = millis();
}


bool buttonPressed(
  ButtonInput &button,
  unsigned long now
) {

  bool reading = digitalRead(button.pin);

  if (reading != button.lastReading) {

    button.lastChange = now;
    button.lastReading = reading;
  }


  if (
    now - button.lastChange >= DEBOUNCE_MS &&
    reading != button.stableState
  ) {

    button.stableState = reading;

    if (button.stableState == LOW) {
      return true;
    }
  }

  return false;
}


// =====================================================
// 13. ОБЪЕКТЫ СИСТЕМЫ
// =====================================================

SensorManager sensorMgr;

DataProcessor dataProc;


RelayManager relayZone1(
  PIN_RELAY_1,
  PIN_LED_1
);


RelayManager relayZone2(
  PIN_RELAY_2,
  PIN_LED_2
);


IrrigationController zone1Ctrl(
  relayZone1,
  "Зона 1"
);


IrrigationController zone2Ctrl(
  relayZone2,
  "Зона 2"
);


unsigned long lastTick = 0;


// =====================================================
// 14. ПОДКЛЮЧЕНИЕ WI-FI
// =====================================================

void startWiFi() {

  Serial.println();
  Serial.println("[Wi-Fi] Подключение к сети...");

  WiFi.mode(WIFI_STA);

  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD,
    6
  );

  lastWiFiAttempt = millis();
}


// Контроль подключения и восстановление Wi-Fi

void maintainWiFi(unsigned long now) {

  if (WiFi.status() == WL_CONNECTED) {

    if (!wifiWasConnected) {

      wifiWasConnected = true;

      Serial.println("[Wi-Fi] Подключение установлено.");

      Serial.print("[Wi-Fi] IP-адрес: ");
      Serial.println(WiFi.localIP());
    }

    return;
  }


  if (wifiWasConnected) {

    wifiWasConnected = false;

    Serial.println("[Wi-Fi] Соединение потеряно.");
  }


  if (
    now - lastWiFiAttempt >= WIFI_RETRY_INTERVAL
  ) {

    Serial.println("[Wi-Fi] Повторная попытка подключения.");

    WiFi.disconnect();

    WiFi.begin(
      WIFI_SSID,
      WIFI_PASSWORD,
      6
    );

    lastWiFiAttempt = now;
  }
}


// =====================================================
// 15. ПОДКЛЮЧЕНИЕ MQTT
// =====================================================

void maintainMQTT(unsigned long now) {

  // Без Wi-Fi MQTT не подключается

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }


  // Если соединение уже установлено,
  // обслуживаем MQTT-клиент

  if (mqttClient.connected()) {

    mqttClient.loop();

    return;
  }


  // Сообщение о потере MQTT

  if (mqttWasConnected) {

    mqttWasConnected = false;

    Serial.println("[MQTT] Соединение потеряно.");
  }


  // Ограничиваем частоту повторных подключений

  if (
    now - lastMqttAttempt < MQTT_RETRY_INTERVAL
  ) {

    return;
  }


  lastMqttAttempt = now;


  Serial.println("[MQTT] Подключение к брокеру...");


  String clientId =
    "VineyardSmart-ESP32-" +
    String((uint32_t)(ESP.getEfuseMac() & 0xFFFFFF), HEX);


  bool connected = mqttClient.connect(
    clientId.c_str(),
    MQTT_TOPIC_STATUS,
    0,
    true,
    "offline"
  );


  if (connected) {

    mqttWasConnected = true;

    Serial.println("[MQTT] Подключение установлено.");

    mqttClient.publish(
      MQTT_TOPIC_STATUS,
      "online",
      true
    );
  }

  else {

    Serial.print("[MQTT] Ошибка подключения. Код: ");
    Serial.println(mqttClient.state());
  }
}


// =====================================================
// 16. ПУБЛИКАЦИЯ ТЕЛЕМЕТРИИ В MQTT
// =====================================================

void publishTelemetry(
  SensorData &data,
  bool manualMode,
  bool raining
) {

  if (!mqttClient.connected()) {
    return;
  }


  char payload[512];


  // Формируем JSON-сообщение

  snprintf(
    payload,
    sizeof(payload),

    "{"
      "\"device\":\"VineyardSmart-ESP32\","
      "\"mode\":\"%s\","

      "\"zone1\":{"
        "\"soil\":%.1f,"
        "\"soil_adc\":%d,"
        "\"irrigation\":%s,"
        "\"sensor_valid\":%s"
      "},"

      "\"zone2\":{"
        "\"soil\":%.1f,"
        "\"soil_adc\":%d,"
        "\"irrigation\":%s,"
        "\"sensor_valid\":%s"
      "},"

      "\"air\":{"
        "\"temperature\":%.1f,"
        "\"humidity\":%.1f,"
        "\"valid\":%s"
      "},"

      "\"light_adc\":%d,"
      "\"rain_adc\":%d,"
      "\"raining\":%s"

    "}",

    manualMode ? "MANUAL" : "AUTO",

    data.soil1,
    data.soil1Raw,
    relayZone1.getState() ? "true" : "false",
    data.soil1Valid ? "true" : "false",

    data.soil2,
    data.soil2Raw,
    relayZone2.getState() ? "true" : "false",
    data.soil2Valid ? "true" : "false",

    data.airTemp,
    data.airHum,
    data.airValid ? "true" : "false",

    data.lightRaw,
    data.rainRaw,
    raining ? "true" : "false"
  );


  bool published = mqttClient.publish(
    MQTT_TOPIC_TELEMETRY,
    payload
  );


  if (published) {

    Serial.println("[MQTT] Телеметрия отправлена.");

    Serial.println(payload);
  }

  else {

    Serial.println("[MQTT] Ошибка публикации телеметрии.");
  }
}


// =====================================================
// 17. ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ
// =====================================================

void setup() {

  Serial.begin(115200);


  // Инициализация датчиков

  sensorMgr.begin();


  // Инициализация исполнительных каналов

  relayZone1.begin();
  relayZone2.begin();


  // Переключатель режимов

  pinMode(PIN_MODE_SWITCH, INPUT);


  // Инициализация кнопок

  beginButton(button1, PIN_BUTTON_1);
  beginButton(button2, PIN_BUTTON_2);


  // Настройка MQTT-клиента

  mqttClient.setServer(
    MQTT_SERVER,
    MQTT_PORT
  );

  mqttClient.setBufferSize(512);

  mqttClient.setKeepAlive(30);

  mqttClient.setSocketTimeout(3);


  Serial.println();

  Serial.println("================================");
  Serial.println(" СИСТЕМА УПРАВЛЕНИЯ ВИНОГРАДНИКОМ");
  Serial.println(" ESP32: система запущена");
  Serial.println("================================");

  Serial.println("Режимы AUTO и MANUAL доступны.");


  // Запуск Wi-Fi

  startWiFi();
}


// =====================================================
// 18. ОСНОВНОЙ ЦИКЛ ПРОГРАММЫ
// =====================================================

void loop() {

  unsigned long currentMillis = millis();


  // ===============================================
  // WI-FI И MQTT
  // ===============================================

  maintainWiFi(currentMillis);

  maintainMQTT(currentMillis);


  // ===============================================
  // ОПРЕДЕЛЕНИЕ РЕЖИМА УПРАВЛЕНИЯ
  // ===============================================

  bool manualMode =
    digitalRead(PIN_MODE_SWITCH) == LOW;


  // ===============================================
  // ОБРАБОТКА КНОПОК
  // ===============================================

  bool zone1ButtonPressed =
    buttonPressed(button1, currentMillis);

  bool zone2ButtonPressed =
    buttonPressed(button2, currentMillis);


  if (manualMode) {

    if (zone1ButtonPressed) {

      zone1Ctrl.toggleManualRequest();

      Serial.println(
        "[Зона 1] Изменена ручная команда."
      );
    }


    if (zone2ButtonPressed) {

      zone2Ctrl.toggleManualRequest();

      Serial.println(
        "[Зона 2] Изменена ручная команда."
      );
    }
  }


  // ===============================================
  // ОСНОВНОЙ ЦИКЛ МОНИТОРИНГА
  // ===============================================

  if (
    currentMillis - lastTick >= LOOP_INTERVAL
  ) {

    lastTick = currentMillis;


    // Считывание датчиков

    SensorData data = sensorMgr.readAll();


    // Проверка почвы

    bool soil1Ok =
      data.soil1Valid &&
      dataProc.validateSoil(data.soil1);

    bool soil2Ok =
      data.soil2Valid &&
      dataProc.validateSoil(data.soil2);


    // Проверка воздуха

    bool airOk =
      dataProc.validateAir(data);


    // Определение дождя

    bool raining =
      dataProc.isRaining(data.rainRaw);


    // =============================================
    // УПРАВЛЕНИЕ ПЕРВОЙ ЗОНОЙ
    // =============================================

    zone1Ctrl.update(
      data.soil1,
      soil1Ok,
      raining,
      manualMode,
      currentMillis
    );


    // =============================================
    // УПРАВЛЕНИЕ ВТОРОЙ ЗОНОЙ
    // =============================================

    zone2Ctrl.update(
      data.soil2,
      soil2Ok,
      raining,
      manualMode,
      currentMillis
    );


    // =============================================
    // МОНИТОРИНГ
    // =============================================

    Serial.println();

    Serial.println("--------- МОНИТОРИНГ ---------");


    Serial.printf(
      "Режим управления: %s\n",
      manualMode ? "MANUAL" : "AUTO"
    );


    Serial.printf(
      "Почва, зона 1: %.1f%% (ADC: %d) | Полив: %s\n",
      data.soil1,
      data.soil1Raw,
      relayZone1.getState() ? "ВКЛ" : "ВЫКЛ"
    );


    Serial.printf(
      "Почва, зона 2: %.1f%% (ADC: %d) | Полив: %s\n",
      data.soil2,
      data.soil2Raw,
      relayZone2.getState() ? "ВКЛ" : "ВЫКЛ"
    );


    if (airOk) {

      Serial.printf(
        "Температура воздуха: %.1f C\n",
        data.airTemp
      );

      Serial.printf(
        "Влажность воздуха: %.1f%%\n",
        data.airHum
      );
    }

    else {

      Serial.println(
        "ОШИБКА: нет корректных данных DHT22"
      );
    }


    Serial.printf(
      "Освещенность: %d ADC | %s\n",
      data.lightRaw,
      dataProc.analyzeLight(data.lightRaw).c_str()
    );


    Serial.printf(
      "Осадки: %d ADC | %s\n",
      data.rainRaw,
      dataProc.analyzeRain(data.rainRaw).c_str()
    );


    Serial.printf(
      "Полив по погодным условиям: %s\n",
      raining ? "ЗАПРЕЩЕН (дождь)" : "РАЗРЕШЕН"
    );


    Serial.printf(
      "Датчик почвы, зона 1: %s\n",
      soil1Ok ? "ДАННЫЕ КОРРЕКТНЫ" : "ОШИБКА"
    );


    Serial.printf(
      "Датчик почвы, зона 2: %s\n",
      soil2Ok ? "ДАННЫЕ КОРРЕКТНЫ" : "ОШИБКА"
    );


    // =============================================
    // ПУБЛИКАЦИЯ ДАННЫХ В MQTT
    // =============================================

    publishTelemetry(
      data,
      manualMode,
      raining
    );


    Serial.println("------------------------------");
  }

  // delay() не используется.
  // Локальное управление продолжает работать
  // независимо от состояния сетевого соединения.
}
