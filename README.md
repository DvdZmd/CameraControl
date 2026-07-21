# 🎥 CameraControl - Plataforma IoT para Raspberry Pi

**CameraControl** es una plataforma IoT completa construida sobre Python y Flask, diseñada para el control avanzado de cámaras en una Raspberry Pi. Va más allá de un simple servidor de streaming, integrando control de movimiento pan/tilt a través de un **ESP32 con BLE**, y gestión de dispositivos inteligentes a través de la API de **Tuya**.

## 🚀 Features

### Cámara y Vídeo
- **Live Streaming MJPEG**: Stream de vídeo en tiempo real, de baja latencia, accesible desde cualquier navegador web.
- **Captura de Imágenes**: Toma de fotos en alta resolución.
- **Fotografía Timelapse**: Captura automatizada de imágenes en intervalos configurables.
- **Controles Avanzados de Cámara**: Ajuste de resolución, rotación, brillo, contraste, saturación, exposición y más.

### Control de Hardware y IoT
- **Control Pan/Tilt (ESP32)**: Manejo preciso de un cabezal pan/tilt a través de un ESP32, comunicado por Bluetooth Low Energy (BLE).
- **Integración con Tuya**: Controla dispositivos inteligentes (como enchufes) registrados en la plataforma Tuya/Smart Life.
- **Arquitectura Modular**: El sistema puede funcionar sin el ESP32 o Tuya, degradando su funcionalidad de forma controlada.

### Sistema y API
- **API RESTful Completa**: Endpoints para todas las funcionalidades, incluyendo cámara, ESP32 y Tuya.
- **Configuración Segura**: Gestión de secretos (API keys, contraseñas) mediante variables de entorno y archivos `.env`.
- **Persistencia de Datos**: Uso de una base de datos SQLite para almacenar configuraciones.
- **Logging Detallado**: Registros de actividad y errores para un diagnóstico sencillo.

## 🛠️ Hardware Requirements

- Raspberry Pi (3B+, 4, or newer recommended)
- Raspberry Pi Camera Module (v1, v2, or HQ Camera)
- MicroSD card (16GB+ recommended)

### Opcional (para funcionalidades extendidas)
- **Para Pan/Tilt**:
  - Un microcontrolador ESP32.
  - Un cabezal pan/tilt con servos (ej. SG90).
  - Fuente de alimentación externa para los servos.
- **Para control de energía**:
  - Un enchufe inteligente compatible con Tuya / Smart Life.

## 📦 Installation

1.  **Clonar el Repositorio**
    ```bash
    git clone https://github.com/DvdZmd/CameraControl.git
    cd CameraControl
    ```

2.  **Ejecutar el Script de Instalación**
    Este script se encarga de crear el entorno virtual, instalar dependencias y preparar los directorios necesarios.
    ```bash
    ./setup.sh
    ```

3.  **Configurar Secretos**
    La aplicación ahora requiere un archivo `.env` para gestionar las claves de API y otros secretos de forma segura.
    ```bash
    # Copia la plantilla de ejemplo
    cp .env.example .env

    # Edita el archivo .env con tus valores
    nano .env
    ```
    Deberás rellenar como mínimo la `FLASK_SECRET_KEY`. Puedes generar una con `python -c 'import os; print(os.urandom(24).hex())'`.
    Para usar la integración con Tuya, rellena las credenciales correspondientes.

4.  **Activar el Entorno Virtual**
    ```bash
    source venv/bin/activate
    ```

5.  **Iniciar la Aplicación**
    ```bash
    python app.py
    ```

La aplicación estará disponible en `http://<IP_DE_TU_PI>:5000`.

## 🚀 Usage

### API Endpoints

La aplicación expone una API RESTful para controlar todas sus funciones. Los prefijos principales son:

- `/api/camera/`: Endpoints para el control de la cámara, streaming y capturas.
- `/api/esp32/`: Endpoints para la comunicación con el ESP32 (pan/tilt).
- `/api/tuya/`: Endpoints para interactuar con dispositivos Tuya.
- `/api/admin/`: Endpoints para la administración del sistema.

Consulta el código en `routes/` para ver la definición detallada de cada endpoint.

## 📁 Project Structure

```
CameraControl/
├── app.py                 # Main Flask application
├── app_factory.py         # Application factory and configuration
├── config.py              # Configuration constants and classes
├── requirements.txt       # Python dependencies
├── setup.sh              # Automated setup script
├── README.md             # This file
├── camera/
│   ├── picam.py          # Camera initialization and configuration
│   └── timelapse.py      # Timelapse functionality
├── database/
│   ├── app.db           # SQLite database (auto-created)
│   └── models.py        # Database models
├── logs/
│   ├── db_logger.py     # Database error logging
│   └── logging_config.py # Logging configuration
└── routes/
    └── camera_routes.py  # Flask routes and API endpoints
```

## ⚙️ Configuration

### Key Configuration Files

- **`config.py`**: Main configuration constants
- **`database/models.py`**: Database schema
- **`logs/logging_config.py`**: Logging setup

### Important Settings

```python
# Camera settings
CAMERA_WIDTH = 640          # Default stream width
CAMERA_HEIGHT = 480         # Default stream height  
FRAME_RATE = 60            # Camera frame rate (FPS)
NOISE_REDUCTION_MODE = 2   # Camera noise reduction

# File paths
LOG_FILE_PATH = "/home/pi/Desktop/logs/server.log"
TIMELAPSE_DIR = "/home/pi/Desktop/timelapse"

# Available resolutions for streaming and capture
AVAILABLE_RESOLUTIONS = [
    (640, 480),    # VGA
    (800, 600),    # SVGA
    (1280, 720),   # HD
    (1920, 1080),  # Full HD
    (2592, 1944)   # Max (camera dependent)
]
```

## 🐛 Troubleshooting

### Camera Not Working
```bash
# Check camera detection
libcamera-hello --list-cameras

# Test camera functionality  
libcamera-still -o test.jpg

# Verify camera interface is enabled
grep camera /boot/config.txt
```

### Import Errors
```bash
# Ensure virtual environment is active
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Permission Issues
```bash
# Fix directory permissions
sudo chown -R pi:pi /home/pi/Desktop/logs
sudo chown -R pi:pi /home/pi/Desktop/timelapse
chmod 755 /home/pi/Desktop/logs /home/pi/Desktop/timelapse
```

### Network Access Issues
```bash
# Check if Flask is binding to all interfaces
# In app.py, ensure: app.run(host='0.0.0.0', port=5000)

# Find Pi's IP address
hostname -I
```

## 🔧 Development

### Adding New Features
1. Add routes in `routes/camera_routes.py`
2. Update database models in `database/models.py` if needed
3. Add configuration options in `config.py`
4. Update requirements.txt for new dependencies

### Testing
```bash
# Test camera functionality
python -c "from camera.picam import picam2; print('Camera OK' if picam2 else 'Camera Error')"

# Test database
python -c "from database.models import db; print('Database OK')"
```

## 📝 Dependencies

Core dependencies managed in `requirements.txt`:

- **Flask 3.0.0**: Web framework
- **Flask-SQLAlchemy 3.1.1**: Database ORM
- **picamera2 0.3.17**: Raspberry Pi camera interface
- **RpiCamZ**: External Raspberry Pi camera controller library installed from [DvdZmd/rpicam-z](https://github.com/DvdZmd/rpicam-z)
- **opencv-python 4.9.0.80**: Image processing
- **numpy 1.24.3**: Numerical computing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on Raspberry Pi hardware
5. Submit a pull request

## 📄 License

This project is open source. Please check the license file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Verify hardware connections and camera functionality
3. Review log files in `/home/pi/Desktop/logs/server.log`
4. Check database logs in the ErrorLog table

---

**Made for Raspberry Pi Camera Control** 🎥🥧# CameraControl
