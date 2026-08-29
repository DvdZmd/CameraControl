#include <Arduino.h>
#include <ESP32Servo.h>
#include <NimBLEDevice.h>
#include <Preferences.h>

// =====================================================
// CONFIG GENERAL
// =====================================================
static constexpr float FILTER_ALPHA = 0.25f;   // 0..1, más bajo = más filtrado
static constexpr int DEAD_ZONE = 250;          // zona muerta del joystick
static constexpr uint32_t LOOP_INTERVAL_MS = 10;
static constexpr uint32_t BUTTON_DEBOUNCE_MS = 180;
static constexpr uint32_t RETURN_BUTTON_LONG_PRESS_MS = 1200;

// =====================================================
// PINES
// =====================================================
#define SERVO_PAN_PIN   18
#define SERVO_TILT_A    19
#define SERVO_TILT_B    5

#define SPEED_BUTTON    13
#define JOY_BUTTON_X    33
#define JOY_X_PIN       32
#define JOY_Y_PIN       35


// =====================================================
// BLE UUIDs
// =====================================================
static const char* BLE_DEVICE_NAME = "ESP32-PanTiltPro";

// Servicio custom
static const char* SERVICE_UUID        = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
static const char* CHARACTERISTIC_RX   = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"; // WRITE
static const char* CHARACTERISTIC_TX   = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"; // NOTIFY

// =====================================================
// SERVOS
// =====================================================
Servo servoPan;
Servo servoTiltA;
Servo servoTiltB;

const int minPulse = 500;
const int maxPulse = 2400;
const int centerPulse = 1450;

int panPulse   = centerPulse;
int tiltAPulse = centerPulse;
int tiltBPulse = centerPulse;

int returnPanPulse   = centerPulse;
int returnTiltAPulse = centerPulse;
int returnTiltBPulse = centerPulse;

// =====================================================
// JOYSTICK / FILTRO
// =====================================================
int centerX = 0;
int centerY = 0;

float filteredX = 0.0f;
float filteredY = 0.0f;
bool filterInitialized = false;

// =====================================================
// VELOCIDAD
// =====================================================
struct SpeedProfile {
  int servoStep;
  int deadZone;
};

SpeedProfile 
speedProfiles[] = {
  {2,  300},  // muy fino
  {5,  280},
  {10, 250},
  {15, 220},
  {20, 180}   // rápido
};

static constexpr int SPEED_PROFILE_COUNT =
  sizeof(speedProfiles) / sizeof(speedProfiles[0]);

int speedMode = 2;
int currentServoStep = 5;
int currentDeadZone = 250;

void applySpeedMode() {
  speedMode = constrain(speedMode, 0, SPEED_PROFILE_COUNT - 1);
  currentServoStep = speedProfiles[speedMode].servoStep;
  currentDeadZone  = speedProfiles[speedMode].deadZone;
}

// =====================================================
// PERSISTENCIA EN NVS
// =====================================================
Preferences preferences;

static constexpr const char* PREF_NAMESPACE = "panTiltPro";
static constexpr const char* PREF_KEY_SPEED = "speed";
static constexpr const char* PREF_KEY_RETURN_PAN = "returnPan";
static constexpr const char* PREF_KEY_RETURN_TILT_A = "returnTiltA";
static constexpr const char* PREF_KEY_RETURN_TILT_B = "returnTiltB";

void loadPersistentSettings() {
  preferences.begin(PREF_NAMESPACE, true);

  speedMode = preferences.getInt(PREF_KEY_SPEED, 2);
  returnPanPulse = preferences.getInt(PREF_KEY_RETURN_PAN, centerPulse);
  returnTiltAPulse = preferences.getInt(PREF_KEY_RETURN_TILT_A, centerPulse);
  returnTiltBPulse = preferences.getInt(PREF_KEY_RETURN_TILT_B, centerPulse);

  preferences.end();

  speedMode = constrain(speedMode, 0, SPEED_PROFILE_COUNT - 1);
  returnPanPulse = constrain(returnPanPulse, minPulse, maxPulse);
  returnTiltAPulse = constrain(returnTiltAPulse, minPulse, maxPulse);
  returnTiltBPulse = constrain(returnTiltBPulse, minPulse, maxPulse);
}

void saveSpeedMode() {
  preferences.begin(PREF_NAMESPACE, false);
  preferences.putInt(PREF_KEY_SPEED, speedMode);
  preferences.end();
}

void saveReturnPosition() {
  returnPanPulse = panPulse;
  returnTiltAPulse = tiltAPulse;
  returnTiltBPulse = tiltBPulse;

  preferences.begin(PREF_NAMESPACE, false);
  preferences.putInt(PREF_KEY_RETURN_PAN, returnPanPulse);
  preferences.putInt(PREF_KEY_RETURN_TILT_A, returnTiltAPulse);
  preferences.putInt(PREF_KEY_RETURN_TILT_B, returnTiltBPulse);
  preferences.end();
}

// =====================================================
// CONTROL BLE
// =====================================================
NimBLECharacteristic* pTxCharacteristic = nullptr;
bool deviceConnected = false;

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

// =====================================================
// UTILIDADES
// =====================================================
void centerServos() {
  panPulse = centerPulse;
  tiltAPulse = centerPulse;
  tiltBPulse = centerPulse;

  servoPan.writeMicroseconds(panPulse);
  servoTiltA.writeMicroseconds(tiltAPulse);
  servoTiltB.writeMicroseconds(tiltBPulse);
}

void moveToReturnPosition() {
  panPulse = constrain(returnPanPulse, minPulse, maxPulse);
  tiltAPulse = constrain(returnTiltAPulse, minPulse, maxPulse);
  tiltBPulse = constrain(returnTiltBPulse, minPulse, maxPulse);

  servoPan.writeMicroseconds(panPulse);
  servoTiltA.writeMicroseconds(tiltAPulse);
  servoTiltB.writeMicroseconds(tiltBPulse);
}

void calibrateJoystick() {
  long sumX = 0;
  long sumY = 0;
  constexpr int samples = 20;

  for (int i = 0; i < samples; i++) {
    sumX += analogRead(JOY_X_PIN);
    sumY += analogRead(JOY_Y_PIN);
    delay(10);
  }

  centerX = sumX / samples;
  centerY = sumY / samples;

  filteredX = centerX;
  filteredY = centerY;
  filterInitialized = true;
}

void applyPanStep(int step) {
  //Serial.print("previous pan ");
  //Serial.println(panPulse); 
  panPulse = constrain(panPulse + step, minPulse, maxPulse);
  //Serial.print("post pan ");
  //Serial.println(panPulse);
  servoPan.writeMicroseconds(panPulse);
}

void applyTiltStep(int step) {
  //Serial.print("previous tilt ");
  //Serial.println(tiltAPulse);
  tiltAPulse = constrain(tiltAPulse + step, minPulse, maxPulse);
  tiltBPulse = constrain(tiltBPulse - step, minPulse, maxPulse);

  //Serial.println("post Tilt ");
  //Serial.println(tiltAPulse);

  servoTiltA.writeMicroseconds(tiltAPulse);
  servoTiltB.writeMicroseconds(tiltBPulse);
}

void notifyState() {
  if (!deviceConnected || pTxCharacteristic == nullptr) return;

  char payload[128];
  snprintf(payload, sizeof(payload),
           "PAN:%d,TILTA:%d,TILTB:%d,SPEED:%d,RPAN:%d,RTILTA:%d,RTILTB:%d",
           panPulse, tiltAPulse, tiltBPulse, speedMode,
           returnPanPulse, returnTiltAPulse, returnTiltBPulse);

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
    //Serial.println("onWrite");
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
      int newMode = cmd.substring(10).toInt();
      if (newMode >= 0 && newMode < SPEED_PROFILE_COUNT) {
        bleSpeedMode = newMode;
      }
    } else if (cmd.startsWith("SET_ABS:")) {
      // Formato: SET_ABS:1500,1450,1450
      int p1 = cmd.indexOf(':');
      int p2 = cmd.indexOf(',', p1 + 1);
      int p3 = cmd.indexOf(',', p2 + 1);

      if (p1 > 0 && p2 > 0 && p3 > 0) {
        int newPan   = cmd.substring(p1 + 1, p2).toInt();
        int newTiltA = cmd.substring(p2 + 1, p3).toInt();
        int newTiltB = cmd.substring(p3 + 1).toInt();

        panPulse   = constrain(newPan,   minPulse, maxPulse);
        tiltAPulse = constrain(newTiltA, minPulse, maxPulse);
        tiltBPulse = constrain(newTiltB, minPulse, maxPulse);

        servoPan.writeMicroseconds(panPulse);
        servoTiltA.writeMicroseconds(tiltAPulse);
        servoTiltB.writeMicroseconds(tiltBPulse);
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

  //Serial.begin(115200);

  servoPan.attach(SERVO_PAN_PIN, minPulse, maxPulse);
  servoTiltA.attach(SERVO_TILT_A, minPulse, maxPulse);
  servoTiltB.attach(SERVO_TILT_B, minPulse, maxPulse);

  pinMode(JOY_BUTTON_X, INPUT_PULLUP);
  pinMode(SPEED_BUTTON, INPUT_PULLUP);

  loadPersistentSettings();
  calibrateJoystick();
  applySpeedMode();
  centerServos();
  setupBLE();
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  static uint32_t lastLoop = 0;
  static uint32_t speedButtonPressedAt = 0;
  static int lastSpeedButtonState = HIGH;
  static uint32_t joyButtonPressedAt = 0;
  static int lastJoyButtonState = HIGH;
  static bool speedLongPressHandled = false;
  static uint32_t lastNotify = 0;

  uint32_t now = millis();
  if (now - lastLoop < LOOP_INTERVAL_MS) {
    return;
  }
  lastLoop = now;

  // ---------------------------------
  // Boton de velocidad: corto = cambiar velocidad, largo = guardar retorno
  // ---------------------------------
  int speedButtonState = digitalRead(SPEED_BUTTON);
  if (speedButtonState == LOW && lastSpeedButtonState == HIGH) {
    speedButtonPressedAt = now;
    speedLongPressHandled = false;
  }

  if (
      speedButtonState == LOW &&
      !speedLongPressHandled &&
      now - speedButtonPressedAt >= RETURN_BUTTON_LONG_PRESS_MS
  ) {
    saveReturnPosition();
    speedLongPressHandled = true;
    notifyState();
  }

  if (
      speedButtonState == HIGH &&
      lastSpeedButtonState == LOW &&
      !speedLongPressHandled &&
      now - speedButtonPressedAt > BUTTON_DEBOUNCE_MS
  ) {
    speedMode = (speedMode + 1) % SPEED_PROFILE_COUNT;
    applySpeedMode();
    saveSpeedMode();
    notifyState();
  }
  lastSpeedButtonState = speedButtonState;

  // ---------------------------------
  // Boton del joystick: volver a la posicion guardada
  // ---------------------------------
  int joyButtonState = digitalRead(JOY_BUTTON_X);
  if (joyButtonState == LOW && lastJoyButtonState == HIGH) {
    joyButtonPressedAt = now;
  }

  if (
      joyButtonState == HIGH &&
      lastJoyButtonState == LOW &&
      now - joyButtonPressedAt > BUTTON_DEBOUNCE_MS
  ) {
    moveToReturnPosition();
    bleCommand = CommandType::NONE;
    notifyState();
  }
  lastJoyButtonState = joyButtonState;

  // ---------------------------------
  // Cambios de velocidad via BLE
  // ---------------------------------
  if (bleSpeedMode >= 0) {
    if (speedMode != bleSpeedMode) {
      speedMode = bleSpeedMode;
      applySpeedMode();
      saveSpeedMode();
      notifyState();
    }
    bleSpeedMode = -1;
  }

  // ---------------------------------
  // Si hay comando BLE, tiene prioridad
  // ---------------------------------
  if (bleCommand != CommandType::NONE) {
    //Serial.println("bleCommand");
    switch (bleCommand) {
      case CommandType::PAN_LEFT:
        //Serial.println("PAN_LEFT");
        applyPanStep(currentServoStep);
        break;
      case CommandType::PAN_RIGHT:
      //Serial.println("PAN_RIGHT");
        applyPanStep(-currentServoStep);
        break;
      case CommandType::TILT_UP:
      //Serial.println("TILT_UP");
        applyTiltStep(currentServoStep);
        break;
      case CommandType::TILT_DOWN:
      //Serial.println("TILT_DOWN");
        applyTiltStep(-currentServoStep);
        break;
      case CommandType::CENTER:
      //Serial.println("CENTER");
        centerServos();
        bleCommand = CommandType::NONE;
        break;
      case CommandType::STOP:
      //Serial.println("STOP");
        bleCommand = CommandType::NONE;
        break;
      case CommandType::NONE:
      default:
      //Serial.println("default");
        break;
    }
    bleCommand = CommandType::NONE;
  } else if (joyButtonState == HIGH) {
    // ---------------------------------
    // Control local por joystick
    // ---------------------------------
    int rawX = analogRead(JOY_X_PIN);
    int rawY = analogRead(JOY_Y_PIN);

    if (!filterInitialized) {
      filteredX = rawX;
      filteredY = rawY;
      filterInitialized = true;
    }

    filteredX = FILTER_ALPHA * rawX + (1.0f - FILTER_ALPHA) * filteredX;
    filteredY = FILTER_ALPHA * rawY + (1.0f - FILTER_ALPHA) * filteredY;

    int deltaX = static_cast<int>(filteredX) - centerX;
    int deltaY = static_cast<int>(filteredY) - centerY;

    if (abs(deltaX) < currentDeadZone) deltaX = 0;
    if (abs(deltaY) < currentDeadZone) deltaY = 0;

    if (deltaX > 0) {
      applyPanStep(currentServoStep);
    } else if (deltaX < 0) {
      applyPanStep(-currentServoStep);
    }

    if (deltaY > 0) {
      applyTiltStep(currentServoStep);
    } else if (deltaY < 0) {
      applyTiltStep(-currentServoStep);
    }
  }

  // ---------------------------------
  // Telemetría BLE periódica
  // ---------------------------------
  if (deviceConnected && (now - lastNotify > 250)) {
    notifyState();
    lastNotify = now;
  }
}
