#include <Arduino.h>
#include <ESP32Servo.h>
#include <NimBLEDevice.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>

// =====================================================
// CONFIG GENERAL
// =====================================================
static constexpr uint32_t LOOP_INTERVAL_MS = 10;
static constexpr uint32_t SENSOR_READ_INTERVAL_MS = 2000;
static constexpr uint32_t STATE_NOTIFY_INTERVAL_MS = 250;

// =====================================================
// PINES
// =====================================================
static constexpr int SERVO_PAN_PIN = 22;
static constexpr int SERVO_TILT_PIN = 23;
static constexpr int DS18B20_PIN = 13;      // Evitar GPIO12: es strapping pin en ESP32.
static constexpr int DHT22_PIN = 32;
static constexpr int SOIL_SENSOR_PIN = 34;  // ADC input-only en ESP32.

// Calibrar midiendo el sensor en aire/seco y en agua o suelo muy humedo.
static constexpr int SOIL_DRY_RAW = 3000;
static constexpr int SOIL_WET_RAW = 1200;

// =====================================================
// BLE UUIDs
// =====================================================
static const char* BLE_DEVICE_NAME = "ESP32-CameraHead";

static const char* SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
static const char* CHARACTERISTIC_RX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"; // WRITE
static const char* CHARACTERISTIC_TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"; // NOTIFY

// =====================================================
// SERVOS
// =====================================================
Servo servoPan;
Servo servoTilt;

const int minPulse = 500;
const int maxPulse = 2400;
const int centerPulse = 1450;

int panPulse = centerPulse;
int tiltPulse = centerPulse;

// =====================================================
// SENSORES
// =====================================================
OneWire oneWire(DS18B20_PIN);
DallasTemperature ds18b20(&oneWire);
DHT dht(DHT22_PIN, DHT22);

float ds18b20TempC = NAN;
float dhtTempC = NAN;
float dhtHumidity = NAN;
int soilRaw = 0;
int soilPercent = -1;

// =====================================================
// VELOCIDAD
// =====================================================
struct SpeedProfile {
  int servoStep;
};

SpeedProfile speedProfiles[] = {
  {2},   // muy fino
  {5},
  {10},
  {15},
  {20}   // rapido
};

int speedMode = 2;
int currentServoStep = 10;

void applySpeedMode() {
  speedMode = constrain(speedMode, 0, 4);
  currentServoStep = speedProfiles[speedMode].servoStep;
}

bool parseIntegerStrict(const String& text, int& outValue) {
  if (text.length() == 0) {
    return false;
  }

  int startIndex = 0;
  if (text.charAt(0) == '-') {
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

// =====================================================
// CONTROL BLE
// =====================================================
NimBLECharacteristic* pTxCharacteristic = nullptr;
volatile bool deviceConnected = false;

enum class CommandType {
  NONE,
  PAN_LEFT,
  PAN_RIGHT,
  TILT_UP,
  TILT_DOWN,
  CENTER,
  STOP
};

volatile CommandType bleCommand = CommandType::NONE;
volatile int bleSpeedMode = -1;
volatile bool hasPendingAbs = false;
volatile int pendingPanPulse = centerPulse;
volatile int pendingTiltPulse = centerPulse;

// =====================================================
// UTILIDADES
// =====================================================
void centerServos() {
  panPulse = centerPulse;
  tiltPulse = centerPulse;

  servoPan.writeMicroseconds(panPulse);
  servoTilt.writeMicroseconds(tiltPulse);
}

void applyPanStep(int step) {
  panPulse = constrain(panPulse + step, minPulse, maxPulse);
  servoPan.writeMicroseconds(panPulse);
}

void applyTiltStep(int step) {
  tiltPulse = constrain(tiltPulse + step, minPulse, maxPulse);
  servoTilt.writeMicroseconds(tiltPulse);
}

void readSensors() {
  ds18b20.requestTemperatures();
  float newDsTemp = ds18b20.getTempCByIndex(0);
  if (newDsTemp != DEVICE_DISCONNECTED_C) {
    ds18b20TempC = newDsTemp;
  } else {
    ds18b20TempC = NAN;
  }

  float newDhtTemp = dht.readTemperature();
  float newDhtHumidity = dht.readHumidity();

  // El DHT22 puede devolver NaN si hay ruido o falla de sensor.
  // Mantenemos NaN visible para que la Raspberry Pi detecte el fallo.
  dhtTempC = newDhtTemp;
  dhtHumidity = newDhtHumidity;

  soilRaw = analogRead(SOIL_SENSOR_PIN);
  soilPercent = map(soilRaw, SOIL_DRY_RAW, SOIL_WET_RAW, 0, 100);
  soilPercent = constrain(soilPercent, 0, 100);
}

void notifyState() {
  if (!deviceConnected || pTxCharacteristic == nullptr) return;

  char payload[160];
  snprintf(payload, sizeof(payload),
           "P:%d,T:%d,S:%d,DS:%.2f,DT:%.2f,DH:%.2f,SR:%d,SP:%d",
           panPulse,
           tiltPulse,
           speedMode,
           ds18b20TempC,
           dhtTempC,
           dhtHumidity,
           soilRaw,
           soilPercent);

  pTxCharacteristic->setValue(payload);
  pTxCharacteristic->notify();
}

// =====================================================
// BLE CALLBACKS
// =====================================================
class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
    deviceConnected = true;
  }

  void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
    deviceConnected = false;
    NimBLEDevice::startAdvertising();
  }
};

class RxCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic* pCharacteristic, NimBLEConnInfo& connInfo) override {
    std::string value = pCharacteristic->getValue();
    if (value.empty()) return;

    String cmd = String(value.c_str());
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "PAN_LEFT") {
      bleCommand = CommandType::PAN_LEFT;
    } else if (cmd == "PAN_RIGHT") {
      bleCommand = CommandType::PAN_RIGHT;
    } else if (cmd == "TILT_UP") {
      bleCommand = CommandType::TILT_UP;
    } else if (cmd == "TILT_DOWN") {
      bleCommand = CommandType::TILT_DOWN;
    } else if (cmd == "CENTER") {
      bleCommand = CommandType::CENTER;
    } else if (cmd == "STOP") {
      bleCommand = CommandType::STOP;
    } else if (cmd.startsWith("SET_SPEED:")) {
      int newMode = -1;
      String speedText = cmd.substring(10);
      if (parseIntegerStrict(speedText, newMode) && newMode >= 0 && newMode <= 4) {
        bleSpeedMode = newMode;
      }
    } else if (cmd.startsWith("SET_ABS:")) {
      // Formato: SET_ABS:pan,tilt
      int colonPos = cmd.indexOf(':');
      int commaPos = cmd.indexOf(',', colonPos + 1);
      int secondCommaPos = cmd.indexOf(',', commaPos + 1);

      if (colonPos > 0 &&
          commaPos > colonPos + 1 &&
          commaPos < cmd.length() - 1 &&
          secondCommaPos < 0) {
        int newPan = 0;
        int newTilt = 0;
        String panText = cmd.substring(colonPos + 1, commaPos);
        String tiltText = cmd.substring(commaPos + 1);

        if (parseIntegerStrict(panText, newPan) && parseIntegerStrict(tiltText, newTilt)) {
          pendingPanPulse = constrain(newPan, minPulse, maxPulse);
          pendingTiltPulse = constrain(newTilt, minPulse, maxPulse);
          hasPendingAbs = true;
        }
      }
    }
  }
};

void setupBLE() {
  NimBLEDevice::init(BLE_DEVICE_NAME);

  NimBLEServer* pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  NimBLEService* pService = pServer->createService(SERVICE_UUID);

  NimBLECharacteristic* pRxCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_RX,
    NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR
  );

  pTxCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_TX,
    NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::READ
  );

  pRxCharacteristic->setCallbacks(new RxCallbacks());
  pTxCharacteristic->setValue("READY");

  pService->start();

  NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();

  NimBLEAdvertisementData advData;
  NimBLEAdvertisementData scanData;

  advData.setName(BLE_DEVICE_NAME);
  advData.addServiceUUID(SERVICE_UUID);

  scanData.setName(BLE_DEVICE_NAME);

  pAdvertising->setAdvertisementData(advData);
  pAdvertising->setScanResponseData(scanData);
  pAdvertising->start();
}

// =====================================================
// SETUP
// =====================================================
void setup() {
  delay(500);

  // Serial.begin(115200);

  servoPan.setPeriodHertz(50);
  servoTilt.setPeriodHertz(50);
  servoPan.attach(SERVO_PAN_PIN, minPulse, maxPulse);
  servoTilt.attach(SERVO_TILT_PIN, minPulse, maxPulse);
  centerServos();

  pinMode(SOIL_SENSOR_PIN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(SOIL_SENSOR_PIN, ADC_11db);

  ds18b20.begin();
  // 10 bits reduce el tiempo de conversion respecto a 12 bits.
  ds18b20.setResolution(10);
  dht.begin();
  readSensors();

  applySpeedMode();
  setupBLE();
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  static uint32_t lastLoop = 0;
  static uint32_t lastSensorRead = 0;
  static uint32_t lastNotify = 0;

  uint32_t now = millis();

  if (now - lastSensorRead >= SENSOR_READ_INTERVAL_MS) {
    readSensors();
    lastSensorRead = now;
  }

  if (deviceConnected && (now - lastNotify >= STATE_NOTIFY_INTERVAL_MS)) {
    notifyState();
    lastNotify = now;
  }

  if (now - lastLoop < LOOP_INTERVAL_MS) {
    return;
  }
  lastLoop = now;

  if (bleSpeedMode >= 0) {
    speedMode = bleSpeedMode;
    applySpeedMode();
    bleSpeedMode = -1;
  }

  if (hasPendingAbs) {
    int newPan = pendingPanPulse;
    int newTilt = pendingTiltPulse;

    panPulse = newPan;
    tiltPulse = newTilt;

    servoPan.writeMicroseconds(panPulse);
    servoTilt.writeMicroseconds(tiltPulse);

    hasPendingAbs = false;
  }

  if (bleCommand != CommandType::NONE) {
    switch (bleCommand) {
      case CommandType::PAN_LEFT:
        applyPanStep(currentServoStep);
        break;
      case CommandType::PAN_RIGHT:
        applyPanStep(-currentServoStep);
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
        // El firmware funciona step-per-command; STOP solo limpia comandos pendientes.
        bleCommand = CommandType::NONE;
        break;
      case CommandType::NONE:
      default:
        break;
    }

    bleCommand = CommandType::NONE;
  }
}