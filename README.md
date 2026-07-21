# CameraControl

CameraControl es una plataforma IoT en desarrollo para Raspberry Pi. Expone una
interfaz web Flask para streaming MJPEG, captura y configuración de cámara,
timelapse, control pan/tilt mediante un ESP32 por BLE, lectura de sensores e
integración opcional con Tuya.

El frontend actual usa HTML, CSS y JavaScript servidos por Flask. Se utiliza
como interfaz de desarrollo y está previsto migrarlo a una webapp Vue cuando
las funcionalidades y contratos estén estabilizados.

## Componentes

- Cámara: `rpicam-z`, librería externa y reutilizable instalada desde GitHub.
- Backend: Flask con blueprints por dominio.
- Streaming: MJPEG bajo demanda, sin productor permanente ni cola global.
- Pan/tilt y sensores: ESP32 mediante BLE.
- IoT: Tuya Smart Life mediante `tuya-iot-py-sdk`.
- Persistencia backend: SQLite con Flask-SQLAlchemy.
- Frontend actual: `templates/index.html` y `static/`.

La aplicación intenta degradar de forma controlada cuando falta hardware
opcional. La conexión inicial con Tuya se realiza en segundo plano para no
bloquear el arranque de Flask.

## Firmware ESP32 vigente

El firmware confirmado para desarrollo es:

`PanTiltMicrocontroller/FungiESP.ino`

`PanTiltMicrocontroller/PanTiltPro.ino` se conserva como variante histórica y
no representa el hardware ni el protocolo vigentes.

`FungiESP.ino` controla dos servos y expone sensores DHT22, DS18B20 y humedad de
suelo. Los movimientos son por pasos: cada click envía un comando y produce un
único desplazamiento. Por ahora no existe movimiento continuo al mantener un
botón pulsado.

Comandos BLE soportados:

- `PAN_LEFT`
- `PAN_RIGHT`
- `TILT_UP`
- `TILT_DOWN`
- `CENTER`
- `STOP`
- `SET_SPEED:<0..4>`
- `SET_ABS:<pan>,<tilt>`

Los valores de `SET_ABS` son pulsos en microsegundos y el firmware actual los
limita a `500..2400`. No hay persistencia NVS implementada todavía.

## Estructura real

```text
CameraControl/
├── app.py
├── app_factory.py
├── config.py
├── routes/
│   ├── admin_routes.py
│   ├── camera_routes.py
│   ├── esp32_routes.py
│   └── tuya_routes.py
├── esp32/
│   └── esp32.py
├── tuya/
│   └── tuya_controller.py
├── database/
│   └── models.py
├── logs/
├── templates/
├── static/
├── PanTiltMicrocontroller/
│   ├── FungiESP.ino
│   └── PanTiltPro.ino
├── docs/
└── tests/
```

La implementación de cámara no vive en este repositorio. Se consume como la
dependencia externa `RpiCamZ` definida en `requirements.txt` y sólo debería
modificarse en su propio proyecto cuando sea estrictamente necesario para el
pipeline de cámara.

## Instalación

Requisitos habituales:

- Raspberry Pi OS Bookworm.
- Python 3 con acceso a los paquetes de cámara del sistema.
- Cámara compatible con Picamera2/libcamera.
- Bluetooth y ESP32 sólo para pan/tilt y sensores.
- Credenciales Tuya sólo si se usa esa integración.

```bash
git clone https://github.com/DvdZmd/CameraControl.git
cd CameraControl
./setup.sh
cp .env.example .env
```

Configurar como mínimo una clave Flask persistente:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

Guardar el resultado en `.env`:

```dotenv
FLASK_SECRET_KEY=
```

Las variables Tuya disponibles están documentadas en `.env.example`. El archivo
`.env` está excluido por Git y no debe contenerse en commits.

Para iniciar manualmente:

```bash
source venv/bin/activate
python app.py
```

La interfaz queda disponible en `http://<ip-de-la-pi>:5000`.

## API actual

### Cámara — `/api/camera`

- `GET /camera_status`
- `GET /video_feed`
- `GET /video_feed_sync`
- `GET /take_photo_custom?w=<width>&h=<height>`
- `POST /update_settings`
- `POST /apply_preset`
- `POST /reset`

### ESP32 — `/api/esp32`

- `GET /status`
- `POST /connect`
- `POST /disconnect`
- `POST /command`
- `POST /move`
- `POST /center`
- `POST /speed`

### Tuya — `/api/tuya`

- `GET /status`
- `POST /on`
- `POST /off`

### Administración — `/api/admin`

- `POST /update`

Los contratos concretos y validaciones están definidos por el código en
`routes/`. Antes de cambiar un endpoint deben revisarse también sus consumidores
en `static/js/camera.js`.

## Diagnóstico

Comprobar cámara en Raspberry Pi OS Bookworm:

```bash
rpicam-hello --list-cameras
rpicam-still -o test.jpg
```

Comprobar Flask y MJPEG:

```bash
curl -i http://localhost:5000/
curl -i http://localhost:5000/api/camera/camera_status
curl -v http://localhost:5000/api/camera/video_feed
```

Comprobar Bluetooth:

```bash
rfkill list
systemctl status bluetooth
bluetoothctl show
bluetoothctl scan on
```

Para diagnóstico detallado consultar `docs/TROUBLESHOOTING.md`.

## Pruebas

Pruebas sin hardware:

```bash
python -m unittest discover -s tests -v
```

Estas pruebas no validan físicamente cámara, streaming prolongado, servos,
sensores, BLE ni Tuya. Esos componentes requieren pruebas específicas sobre la
Raspberry Pi y el ESP32 reales.

## Seguridad eléctrica

- No alimentar servos desde 3.3 V de Raspberry Pi o ESP32.
- Usar una fuente adecuada para los servos y GND común con la lógica.
- Confirmar límites mecánicos, orientación y pulsos antes de probar movimiento.
- Probar inicialmente a baja velocidad y vigilar brownouts o desconexiones BLE.

## Documentación técnica

- `docs/ARCHITECTURE.md`
- `docs/CAMERA_PIPELINE.md`
- `docs/ESP32_BLE_PROTOCOL.md`
- `docs/HARDWARE.md`
- `docs/PROJECT_HISTORY.md`
- `docs/SECURITY.md`
- `docs/TROUBLESHOOTING.md`

El código actual es la fuente de verdad. La historia del proyecto se conserva
como contexto, pero no debe imponerse sobre la implementación vigente.
