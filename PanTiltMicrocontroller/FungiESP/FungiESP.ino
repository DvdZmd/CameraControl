#include <Arduino.h>
#include <ESP32Servo.h>
#include <NimBLEDevice.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <Preferences.h>
#include <esp_arduino_version.h>

// =====================================================
// TIPOS Y PROTOTIPOS
// Deben estar antes de cualquier función del archivo .ino
// =====================================================

enum class CommandType : uint8_t {
  NONE,
  PAN_LEFT,
  PAN_RIGHT,
  TILT_UP,
  TILT_DOWN,
  CENTER,
  STOP,
  LIGHT_ON,
  LIGHT_OFF
};

// Prototipos explícitos para evitar problemas con el
// generador automático de prototipos de Arduino.
void queueCommand(CommandType command);
bool consumeCommand(CommandType& command);
void clearPendingMovementCommands();

void queueSpeedMode(int newSpeedMode);
bool consumeSpeedMode(int& newMode);

void queueAbsolutePosition(int newPan, int newTilt);
bool consumeAbsolutePosition(int& newPan, int& newTilt);

void queueLightIntensity(int newIntensity);
bool consumeLightIntensity(int& newIntensity);
void setupLightPwm();
void writeLightIntensity(int intensityPercent);

void loadPersistentState();
void markPersistentStateDirty();
void savePersistentStateNow();
void savePersistentStateIfNeeded(uint32_t now);

// =====================================================
// CONFIGURACIÓN GENERAL
// =====================================================

static constexpr uint32_t LOOP_INTERVAL_MS = 10;
static constexpr uint32_t SERVO_UPDATE_INTERVAL_MS = 20;
static constexpr uint32_t SENSOR_READ_INTERVAL_MS = 2000;
static constexpr uint32_t STATE_NOTIFY_INTERVAL_MS = 250;
static constexpr uint32_t DS18B20_CONVERSION_MS = 200;

// Espera después del último cambio antes de escribir en flash.
// Evita una escritura NVS por cada click o comando BLE.
static constexpr uint32_t PERSIST_SAVE_DELAY_MS = 1500;

// =====================================================
// PINES
// =====================================================

static constexpr int SERVO_PAN_PIN = 22;
static constexpr int SERVO_TILT_PIN = 23;
static constexpr int LED_STRIP_PIN = 21;
static constexpr uint32_t LIGHT_PWM_FREQUENCY_HZ = 20000;
static constexpr uint8_t LIGHT_PWM_RESOLUTION_BITS = 8;
static constexpr uint8_t LIGHT_PWM_CHANNEL = 4;

static constexpr int DS18B20_PIN = 13;
static constexpr int DHT22_PIN = 32;
static constexpr int SOIL_SENSOR_PIN = 34;

// =====================================================
// SENSOR DE SUELO
// =====================================================

static constexpr int SOIL_DRY_RAW = 3000;
static constexpr int SOIL_WET_RAW = 1200;

static constexpr int SOIL_SAMPLE_COUNT = 32;
static constexpr int SOIL_SAMPLE_DELAY_US = 200;

// Valores de diagnóstico.
int soilRaw = 0;
int soilMillivolts = 0;
int soilPercent = -1;
int lightIntensityPercent = 0;

void setupSoilSensor() {
  pinMode(SOIL_SENSOR_PIN, INPUT);

  // ADC del ESP32 clásico: 12 bits, valores 0...4095.
  analogReadResolution(12);

  // Configuración específica del pin.
  analogSetPinAttenuation(
      SOIL_SENSOR_PIN,
      ADC_11db
  );

  // Lecturas iniciales descartadas para estabilizar ADC/multiplexor.
  for (int i = 0; i < 10; i++) {
    analogRead(SOIL_SENSOR_PIN);
    delay(2);
  }
}

int readSoilRawAveraged() {
  uint32_t accumulator = 0;
  int validSamples = 0;

  // Descarta dos lecturas antes del promedio.
  analogRead(SOIL_SENSOR_PIN);
  delayMicroseconds(300);

  analogRead(SOIL_SENSOR_PIN);
  delayMicroseconds(300);

  for (int i = 0; i < SOIL_SAMPLE_COUNT; i++) {
    int sample = analogRead(SOIL_SENSOR_PIN);

    if (sample >= 0 && sample <= 4095) {
      accumulator += static_cast<uint32_t>(sample);
      validSamples++;
    }

    delayMicroseconds(SOIL_SAMPLE_DELAY_US);
  }

  if (validSamples == 0) {
    return -1;
  }

  return static_cast<int>(accumulator / validSamples);
}

int convertSoilRawToPercent(int rawValue) {
  if (rawValue < 0) {
    return -1;
  }

  int percentage = map(
      rawValue,
      SOIL_DRY_RAW,
      SOIL_WET_RAW,
      0,
      100
  );

  return constrain(percentage, 0, 100);
}

void readSoilSensor() {
  soilRaw = readSoilRawAveraged();

  // analogReadMilliVolts realiza otra conversión independiente.
  // Sirve para diferenciar un problema lógico de una entrada realmente a 0 V.
  soilMillivolts = analogReadMilliVolts(SOIL_SENSOR_PIN);

  soilPercent = convertSoilRawToPercent(soilRaw);
}

// =====================================================
// BLE UUIDs
// =====================================================

static const char* BLE_DEVICE_NAME = "ESP32-FungiESP";

static const char* SERVICE_UUID =
    "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";

static const char* CHARACTERISTIC_RX =
    "6E400002-B5A3-F393-E0A9-E50E24DCCA9E";

static const char* CHARACTERISTIC_TX =
    "6E400003-B5A3-F393-E0A9-E50E24DCCA9E";

// =====================================================
// SERVOS
// =====================================================

Servo servoPan;
Servo servoTilt;

static constexpr int SERVO_MIN_PULSE_US = 500;
static constexpr int SERVO_MAX_PULSE_US = 2400;
static constexpr int SERVO_CENTER_PULSE_US = 1450;

// Solo evita escrituras de diferencias extremadamente pequeñas.
// No cambia el tamaño del paso configurado.
static constexpr int SERVO_WRITE_DEADBAND_US = 1;

int panPulse = SERVO_CENTER_PULSE_US;
int tiltPulse = SERVO_CENTER_PULSE_US;

// =====================================================
// VELOCIDAD
// =====================================================

struct SpeedProfile {
  int servoStepUs;
};

static constexpr SpeedProfile speedProfiles[] = {
    {2},   // Muy fino
    {5},
    {10},
    {15},
    {20}   // Rápido
};

static constexpr int SPEED_PROFILE_COUNT =
    sizeof(speedProfiles) / sizeof(speedProfiles[0]);

int speedMode = 2;
int currentServoStep = 10;

// =====================================================
// PERSISTENCIA EN NVS
// =====================================================

Preferences preferences;

static constexpr const char* PREF_NAMESPACE = "cameraHead";
static constexpr const char* PREF_KEY_PAN = "pan";
static constexpr const char* PREF_KEY_TILT = "tilt";
static constexpr const char* PREF_KEY_SPEED = "speed";

bool persistentStateDirty = false;
uint32_t persistentStateChangedAt = 0;

void loadPersistentState() {
  preferences.begin(PREF_NAMESPACE, true);

  int storedPan = preferences.getInt(
      PREF_KEY_PAN,
      SERVO_CENTER_PULSE_US
  );

  int storedTilt = preferences.getInt(
      PREF_KEY_TILT,
      SERVO_CENTER_PULSE_US
  );

  int storedSpeed = preferences.getInt(
      PREF_KEY_SPEED,
      2
  );

  preferences.end();

  panPulse = constrain(
      storedPan,
      SERVO_MIN_PULSE_US,
      SERVO_MAX_PULSE_US
  );

  tiltPulse = constrain(
      storedTilt,
      SERVO_MIN_PULSE_US,
      SERVO_MAX_PULSE_US
  );

  speedMode = constrain(
      storedSpeed,
      0,
      SPEED_PROFILE_COUNT - 1
  );
}

void markPersistentStateDirty() {
  persistentStateDirty = true;
  persistentStateChangedAt = millis();
}

void savePersistentStateNow() {
  preferences.begin(PREF_NAMESPACE, false);

  preferences.putInt(PREF_KEY_PAN, panPulse);
  preferences.putInt(PREF_KEY_TILT, tiltPulse);
  preferences.putInt(PREF_KEY_SPEED, speedMode);

  preferences.end();

  persistentStateDirty = false;

  Serial.printf(
      "Estado guardado: pan=%d tilt=%d speed=%d\n",
      panPulse,
      tiltPulse,
      speedMode
  );
}

void savePersistentStateIfNeeded(uint32_t now) {
  if (!persistentStateDirty) {
    return;
  }

  if (now - persistentStateChangedAt < PERSIST_SAVE_DELAY_MS) {
    return;
  }

  savePersistentStateNow();
}

void applySpeedMode() {
  speedMode = constrain(
      speedMode,
      0,
      SPEED_PROFILE_COUNT - 1
  );

  currentServoStep = speedProfiles[speedMode].servoStepUs;
}

// =====================================================
// SENSORES
// =====================================================

OneWire oneWire(DS18B20_PIN);
DallasTemperature ds18b20(&oneWire);
DHT dht(DHT22_PIN, DHT22);

float ds18b20TempC = NAN;
float dhtTempC = NAN;
float dhtHumidity = NAN;

bool dsConversionPending = false;
uint32_t dsConversionStartedAt = 0;
uint32_t lastDsConversionRequest = 0;

// =====================================================
// BLE
// =====================================================

NimBLECharacteristic* pTxCharacteristic = nullptr;

volatile bool deviceConnected = false;

// CommandType ya fue declarado al inicio del archivo.

portMUX_TYPE commandMux = portMUX_INITIALIZER_UNLOCKED;

volatile CommandType pendingCommand = CommandType::NONE;
volatile bool commandAvailable = false;

volatile bool pendingSpeedAvailable = false;
volatile int pendingSpeedMode = -1;

volatile bool pendingAbsAvailable = false;
volatile int pendingAbsPan = SERVO_CENTER_PULSE_US;
volatile int pendingAbsTilt = SERVO_CENTER_PULSE_US;

volatile bool pendingLightAvailable = false;
volatile int pendingLightIntensity = 0;

// =====================================================
// UTILIDADES
// =====================================================

bool parseIntegerStrict(const String& text, int& outValue) {
  if (text.length() == 0) {
    return false;
  }

  int startIndex = 0;

  if (text.charAt(0) == '-' || text.charAt(0) == '+') {
    if (text.length() == 1) {
      return false;
    }

    startIndex = 1;
  }

  for (int i = startIndex; i < text.length(); i++) {
    if (!isDigit(text.charAt(i))) {
      return false;
    }
  }

  outValue = text.toInt();
  return true;
}

void setupLightPwm() {
  // Fija un estado seguro antes de conectar el periférico LEDC. Esto evita que
  // la base del transistor quede flotante durante la inicialización Arduino.
  pinMode(LED_STRIP_PIN, OUTPUT);
  digitalWrite(LED_STRIP_PIN, LOW);

#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(
      LED_STRIP_PIN,
      LIGHT_PWM_FREQUENCY_HZ,
      LIGHT_PWM_RESOLUTION_BITS
  );
#else
  ledcSetup(
      LIGHT_PWM_CHANNEL,
      LIGHT_PWM_FREQUENCY_HZ,
      LIGHT_PWM_RESOLUTION_BITS
  );
  ledcAttachPin(LED_STRIP_PIN, LIGHT_PWM_CHANNEL);
#endif

  writeLightIntensity(0);
}

void writeLightIntensity(int intensityPercent) {
  lightIntensityPercent = constrain(intensityPercent, 0, 100);
  const uint32_t maxDuty =
      (1UL << LIGHT_PWM_RESOLUTION_BITS) - 1UL;
  const uint32_t duty = map(
      lightIntensityPercent,
      0,
      100,
      0,
      maxDuty
  );

#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(LED_STRIP_PIN, duty);
#else
  ledcWrite(LIGHT_PWM_CHANNEL, duty);
#endif
}

// =====================================================
// CONTROL DE SERVOS
// =====================================================

void attachServos() {
  servoPan.setPeriodHertz(50);
  servoTilt.setPeriodHertz(50);

  servoPan.attach(
      SERVO_PAN_PIN,
      SERVO_MIN_PULSE_US,
      SERVO_MAX_PULSE_US
  );

  servoTilt.attach(
      SERVO_TILT_PIN,
      SERVO_MIN_PULSE_US,
      SERVO_MAX_PULSE_US
  );
}

void writePanPulse(int newPulse) {
  newPulse = constrain(
      newPulse,
      SERVO_MIN_PULSE_US,
      SERVO_MAX_PULSE_US
  );

  if (abs(newPulse - panPulse) < SERVO_WRITE_DEADBAND_US) {
    return;
  }

  panPulse = newPulse;
  servoPan.writeMicroseconds(panPulse);
  markPersistentStateDirty();
}

void writeTiltPulse(int newPulse) {
  newPulse = constrain(
      newPulse,
      SERVO_MIN_PULSE_US,
      SERVO_MAX_PULSE_US
  );

  if (abs(newPulse - tiltPulse) < SERVO_WRITE_DEADBAND_US) {
    return;
  }

  tiltPulse = newPulse;
  servoTilt.writeMicroseconds(tiltPulse);
  markPersistentStateDirty();
}

void centerServos() {
  panPulse = SERVO_CENTER_PULSE_US;
  tiltPulse = SERVO_CENTER_PULSE_US;

  servoPan.writeMicroseconds(panPulse);
  servoTilt.writeMicroseconds(tiltPulse);
  markPersistentStateDirty();
}

void applyPanStep(int stepUs) {
  writePanPulse(panPulse + stepUs);
}

void applyTiltStep(int stepUs) {
  writeTiltPulse(tiltPulse + stepUs);
}

void setAbsoluteServoPositions(int newPan, int newTilt) {
  writePanPulse(newPan);
  writeTiltPulse(newTilt);
}

// =====================================================
// SENSORES
// =====================================================

void requestDs18b20Conversion(uint32_t now) {
  ds18b20.requestTemperatures();

  dsConversionStartedAt = now;
  lastDsConversionRequest = now;
  dsConversionPending = true;
}

void updateDs18b20(uint32_t now) {
  if (
      dsConversionPending &&
      now - dsConversionStartedAt >= DS18B20_CONVERSION_MS
  ) {
    float newTemperature = ds18b20.getTempCByIndex(0);

    if (
        newTemperature != DEVICE_DISCONNECTED_C &&
        newTemperature >= -55.0f &&
        newTemperature <= 125.0f
    ) {
      ds18b20TempC = newTemperature;
    } else {
      ds18b20TempC = NAN;
    }

    dsConversionPending = false;
  }

  if (
      !dsConversionPending &&
      now - lastDsConversionRequest >= SENSOR_READ_INTERVAL_MS
  ) {
    requestDs18b20Conversion(now);
  }
}

void readDhtAndSoil() {
  dhtTempC = dht.readTemperature();
  dhtHumidity = dht.readHumidity();

  readSoilSensor();
}

// =====================================================
// TELEMETRÍA BLE
// =====================================================

void notifyState() {
  if (!deviceConnected || pTxCharacteristic == nullptr) {
    return;
  }

  char payload[160];

  snprintf(
      payload,
      sizeof(payload),
      "P:%d,T:%d,S:%d,DS:%.2f,DT:%.2f,DH:%.2f,SR:%d,SP:%d,L:%d",
      panPulse,
      tiltPulse,
      speedMode,
      ds18b20TempC,
      dhtTempC,
      dhtHumidity,
      soilRaw,
      soilPercent,
      lightIntensityPercent
  );

  pTxCharacteristic->setValue(payload);
  pTxCharacteristic->notify();
}

// =====================================================
// COLA SIMPLE DE COMANDOS
// =====================================================

void queueCommand(CommandType command) {
  portENTER_CRITICAL(&commandMux);

  pendingCommand = command;
  commandAvailable = true;

  portEXIT_CRITICAL(&commandMux);
}

void queueSpeedMode(int newSpeedMode) {
  portENTER_CRITICAL(&commandMux);

  pendingSpeedMode = newSpeedMode;
  pendingSpeedAvailable = true;

  portEXIT_CRITICAL(&commandMux);
}

void queueAbsolutePosition(int newPan, int newTilt) {
  portENTER_CRITICAL(&commandMux);

  pendingAbsPan = newPan;
  pendingAbsTilt = newTilt;
  pendingAbsAvailable = true;

  portEXIT_CRITICAL(&commandMux);
}

void queueLightIntensity(int newIntensity) {
  portENTER_CRITICAL(&commandMux);

  pendingLightIntensity = newIntensity;
  pendingLightAvailable = true;

  portEXIT_CRITICAL(&commandMux);
}

bool consumeCommand(CommandType& command) {
  bool available = false;

  portENTER_CRITICAL(&commandMux);

  if (commandAvailable) {
    command = pendingCommand;

    pendingCommand = CommandType::NONE;
    commandAvailable = false;

    available = true;
  }

  portEXIT_CRITICAL(&commandMux);

  return available;
}

bool consumeSpeedMode(int& newMode) {
  bool available = false;

  portENTER_CRITICAL(&commandMux);

  if (pendingSpeedAvailable) {
    newMode = pendingSpeedMode;

    pendingSpeedMode = -1;
    pendingSpeedAvailable = false;

    available = true;
  }

  portEXIT_CRITICAL(&commandMux);

  return available;
}

bool consumeAbsolutePosition(int& newPan, int& newTilt) {
  bool available = false;

  portENTER_CRITICAL(&commandMux);

  if (pendingAbsAvailable) {
    newPan = pendingAbsPan;
    newTilt = pendingAbsTilt;

    pendingAbsAvailable = false;

    available = true;
  }

  portEXIT_CRITICAL(&commandMux);

  return available;
}

bool consumeLightIntensity(int& newIntensity) {
  bool available = false;

  portENTER_CRITICAL(&commandMux);

  if (pendingLightAvailable) {
    newIntensity = pendingLightIntensity;
    pendingLightAvailable = false;
    available = true;
  }

  portEXIT_CRITICAL(&commandMux);

  return available;
}

void clearPendingMovementCommands() {
  portENTER_CRITICAL(&commandMux);

  pendingCommand = CommandType::NONE;
  commandAvailable = false;

  portEXIT_CRITICAL(&commandMux);
}

// =====================================================
// BLE CALLBACKS
// =====================================================

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(
      NimBLEServer* pServer,
      NimBLEConnInfo& connInfo
  ) override {
    deviceConnected = true;
  }

  void onDisconnect(
      NimBLEServer* pServer,
      NimBLEConnInfo& connInfo,
      int reason
  ) override {
    deviceConnected = false;

    // En movimiento por pasos no hay movimiento continuo.
    // Solo elimina cualquier orden que todavía no se haya procesado.
    clearPendingMovementCommands();

    NimBLEDevice::startAdvertising();
  }
};

class RxCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(
      NimBLECharacteristic* pCharacteristic,
      NimBLEConnInfo& connInfo
  ) override {
    std::string value = pCharacteristic->getValue();

    if (value.empty()) {
      return;
    }

    String cmd(value.c_str());

    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "PAN_LEFT") {
      queueCommand(CommandType::PAN_LEFT);
      return;
    }

    if (cmd == "PAN_RIGHT") {
      queueCommand(CommandType::PAN_RIGHT);
      return;
    }

    if (cmd == "TILT_UP") {
      queueCommand(CommandType::TILT_UP);
      return;
    }

    if (cmd == "TILT_DOWN") {
      queueCommand(CommandType::TILT_DOWN);
      return;
    }

    if (cmd == "CENTER") {
      queueCommand(CommandType::CENTER);
      return;
    }

    if (cmd == "STOP") {
      queueCommand(CommandType::STOP);
      return;
    }

    if (cmd == "LIGHT_ON") {
      queueCommand(CommandType::LIGHT_ON);
      return;
    }

    if (cmd == "LIGHT_OFF") {
      queueCommand(CommandType::LIGHT_OFF);
      return;
    }

    if (cmd.startsWith("SET_LIGHT:")) {
      String intensityText = cmd.substring(
          strlen("SET_LIGHT:")
      );
      intensityText.trim();

      int newIntensity = -1;
      if (
          parseIntegerStrict(intensityText, newIntensity) &&
          newIntensity >= 0 &&
          newIntensity <= 100
      ) {
        queueLightIntensity(newIntensity);
      }

      return;
    }

    if (cmd.startsWith("SET_SPEED:")) {
      String speedText = cmd.substring(
          strlen("SET_SPEED:")
      );

      speedText.trim();

      int newMode = -1;

      if (
          parseIntegerStrict(speedText, newMode) &&
          newMode >= 0 &&
          newMode < SPEED_PROFILE_COUNT
      ) {
        queueSpeedMode(newMode);
      }

      return;
    }

    if (cmd.startsWith("SET_ABS:")) {
      String valuesText = cmd.substring(
          strlen("SET_ABS:")
      );

      valuesText.trim();

      int commaPos = valuesText.indexOf(',');

      if (
          commaPos <= 0 ||
          commaPos >= valuesText.length() - 1
      ) {
        return;
      }

      // Rechaza más de una coma.
      if (valuesText.indexOf(',', commaPos + 1) >= 0) {
        return;
      }

      String panText = valuesText.substring(0, commaPos);
      String tiltText = valuesText.substring(commaPos + 1);

      panText.trim();
      tiltText.trim();

      int newPan = 0;
      int newTilt = 0;

      if (
          parseIntegerStrict(panText, newPan) &&
          parseIntegerStrict(tiltText, newTilt)
      ) {
        newPan = constrain(
            newPan,
            SERVO_MIN_PULSE_US,
            SERVO_MAX_PULSE_US
        );

        newTilt = constrain(
            newTilt,
            SERVO_MIN_PULSE_US,
            SERVO_MAX_PULSE_US
        );

        queueAbsolutePosition(newPan, newTilt);
      }

      return;
    }
  }
};

// =====================================================
// BLE SETUP
// =====================================================

void setupBLE() {
  NimBLEDevice::init(BLE_DEVICE_NAME);

  NimBLEServer* pServer = NimBLEDevice::createServer();

  pServer->setCallbacks(new ServerCallbacks());

  NimBLEService* pService =
      pServer->createService(SERVICE_UUID);

  NimBLECharacteristic* pRxCharacteristic =
      pService->createCharacteristic(
          CHARACTERISTIC_RX,
          NIMBLE_PROPERTY::WRITE |
          NIMBLE_PROPERTY::WRITE_NR
      );

  pTxCharacteristic =
      pService->createCharacteristic(
          CHARACTERISTIC_TX,
          NIMBLE_PROPERTY::NOTIFY |
          NIMBLE_PROPERTY::READ
      );

  pRxCharacteristic->setCallbacks(new RxCallbacks());

  pTxCharacteristic->setValue("READY");

  pService->start();

  NimBLEAdvertising* pAdvertising =
      NimBLEDevice::getAdvertising();

  NimBLEAdvertisementData advertisementData;
  NimBLEAdvertisementData scanResponseData;

  advertisementData.setName(BLE_DEVICE_NAME);
  advertisementData.addServiceUUID(SERVICE_UUID);

  scanResponseData.setName(BLE_DEVICE_NAME);

  pAdvertising->setAdvertisementData(
      advertisementData
  );

  pAdvertising->setScanResponseData(
      scanResponseData
  );

  pAdvertising->start();
}

// =====================================================
// PROCESAMIENTO DE COMANDOS
// =====================================================

void processConfigurationCommands() {
  int newSpeedMode = -1;

  if (consumeSpeedMode(newSpeedMode)) {
    if (speedMode != newSpeedMode) {
      speedMode = newSpeedMode;
      applySpeedMode();
      savePersistentStateNow();
    }

    notifyState();
  }

  int newPan = 0;
  int newTilt = 0;

  if (consumeAbsolutePosition(newPan, newTilt)) {
    setAbsoluteServoPositions(newPan, newTilt);
  }

  int newLightIntensity = -1;

  if (consumeLightIntensity(newLightIntensity)) {
    writeLightIntensity(newLightIntensity);
    notifyState();
  }
}

void processSingleServoCommand() {
  CommandType command = CommandType::NONE;

  if (!consumeCommand(command)) {
    return;
  }

  // Cada comando se consume exactamente una vez.
  switch (command) {
    case CommandType::PAN_LEFT:
      applyPanStep(-currentServoStep);
      break;

    case CommandType::PAN_RIGHT:
      applyPanStep(currentServoStep);
      break;

    case CommandType::TILT_UP:
      applyTiltStep(currentServoStep);
      break;

    case CommandType::TILT_DOWN:
      applyTiltStep(-currentServoStep);
      break;

    case CommandType::CENTER:
      centerServos();
      break;

    case CommandType::STOP:
      // No existe movimiento continuo.
      // STOP solamente limpia cualquier orden pendiente.
      clearPendingMovementCommands();
      break;

    case CommandType::LIGHT_ON:
      writeLightIntensity(100);
      notifyState();
      break;

    case CommandType::LIGHT_OFF:
      writeLightIntensity(0);
      notifyState();
      break;

    case CommandType::NONE:
    default:
      break;
  }
}

// =====================================================
// SETUP
// =====================================================

void setup() {
  // Debe ser la primera acción de la aplicación. GPIO21 controla un transistor
  // low-side: LOW mantiene apagada la tira mientras inicializa el resto.
  pinMode(LED_STRIP_PIN, OUTPUT);
  digitalWrite(LED_STRIP_PIN, LOW);

  Serial.begin(115200);

  delay(500);

  loadPersistentState();
  applySpeedMode();

  // ESP32Servo también utiliza LEDC. Los servos deben reservar primero sus
  // recursos para que el PWM auxiliar de la luz no interfiera con GPIO22/23.
  attachServos();
  servoPan.writeMicroseconds(panPulse);
  servoTilt.writeMicroseconds(tiltPulse);
  Serial.printf(
      "Servos adjuntos: pan(GPIO%d)=%s tilt(GPIO%d)=%s\n",
      SERVO_PAN_PIN,
      servoPan.attached() ? "si" : "no",
      SERVO_TILT_PIN,
      servoTilt.attached() ? "si" : "no"
  );
 
  // GPIO21 se mantuvo en LOW desde la primera instrucción de setup(). Ahora se
  // adjunta su PWM usando los recursos LEDC restantes.
  setupLightPwm();

  setupSoilSensor();

  ds18b20.begin();
  ds18b20.setResolution(10);

  // Conversión no bloqueante.
  ds18b20.setWaitForConversion(false);

  dht.begin();

  readDhtAndSoil();
  requestDs18b20Conversion(millis());

  setupBLE();

  Serial.printf(
      "Estado restaurado: pan=%d tilt=%d speed=%d\n",
      panPulse,
      tiltPulse,
      speedMode
  );
  Serial.println("ESP32-FungiESP listo");
}

// =====================================================
// LOOP
// =====================================================

void loop() {
  static uint32_t lastGeneralLoop = 0;
  static uint32_t lastServoCommand = 0;
  static uint32_t lastDhtSoilRead = 0;
  static uint32_t lastNotify = 0;

  uint32_t now = millis();

  // Persistencia diferida en NVS.
  savePersistentStateIfNeeded(now);

  // DS18B20 asíncrono.
  updateDs18b20(now);

  // DHT22 y sensor de suelo.
  if (
      now - lastDhtSoilRead >= SENSOR_READ_INTERVAL_MS
  ) {
    lastDhtSoilRead = now;
    readDhtAndSoil();
  }

  // Telemetría.
  if (
      deviceConnected &&
      now - lastNotify >= STATE_NOTIFY_INTERVAL_MS
  ) {
    lastNotify = now;
    notifyState();
  }

  // Configuración general.
  if (
      now - lastGeneralLoop >= LOOP_INTERVAL_MS
  ) {
    lastGeneralLoop = now;
    processConfigurationCommands();
  }

  // Consume como máximo un comando de servo cada 20 ms.
  //
  // Un PAN_LEFT recibido equivale exactamente a:
  // panPulse -= currentServoStep
  //
  // Después de aplicarlo, el comando queda consumido.
  if (
      now - lastServoCommand >= SERVO_UPDATE_INTERVAL_MS
  ) {
    lastServoCommand = now;
    processSingleServoCommand();
  }
}
