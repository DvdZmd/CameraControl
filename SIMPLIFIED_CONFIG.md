# 🎯 Camera Control Project - Simplified Configuration

## What Was Removed

This project has been cleaned up to focus solely on **camera streaming and control** functionality. The following components from the original FungiForge project have been removed:

### ❌ Removed Features:
- **I2C Communications** (`ARDUINO_PAN_TILT`, `ARDUINO_SENSORS`, `I2C_BUS_ID`)
- **Servo Control** (`INVERT_PAN_AXIS`, `INVERT_TILT_AXIS`, pan/tilt functionality)
- **Sensor Reading** (`READ_I2C_SENSORS`, `READ_SERVOS`, sensor logging)
- **Bluetooth/ESP32** (ESP32 BLE configurations)
- **Smart Plug Control** (Tuya smart plug integration)
- **Advanced Logging** (sensor logger, I2C device logging)

### ✅ Current Core Features:
1. **Camera Streaming** - Live MJPEG video feed
2. **Image Capture** - High-quality photo capture
3. **Timelapse** - Automated image capture at intervals
4. **Camera Configuration** - Resolution, rotation, enable/disable
5. **Basic Logging** - Application and error logging
6. **Database** - Configuration persistence

## Current Configuration Structure

```python
# config.py - Simplified Structure

# === GLOBAL CONSTANTS ===
LOG_FILE_PATH = "/home/pi/Desktop/logs/server.log"
LOG_LEVEL = "INFO"

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FRAME_RATE = 60
NOISE_REDUCTION_MODE = 2

TIMELAPSE_DIR = "/home/pi/Desktop/timelapse"
AVAILABLE_RESOLUTIONS = [(640,480), (800,600), (1280,720), (1920,1080), (2592,1944)]

# === DATACLASS CONFIGURATIONS ===
@dataclass
class LoggingConfig: ...

@dataclass  
class CameraConfig: ...

@dataclass
class TimelapseConfig: ...

@dataclass
class AppConfig:
    logging: LoggingConfig
    camera: CameraConfig  
    timelapse: TimelapseConfig
```

## Dependencies Simplified

The `requirements.txt` now contains only essential packages:

```txt
Flask==3.0.0                # Web framework
Flask-SQLAlchemy==3.1.1     # Database ORM  
picamera2==0.3.17          # Raspberry Pi camera
opencv-python==4.9.0.80    # Image processing
numpy==1.24.3              # Numerical computing
SQLAlchemy==2.0.23         # Database
Werkzeug==3.0.1            # Security utilities
```

## API Endpoints (Current)

- `GET /video_feed` - Camera stream
- `GET /capture_image` - Take photo
- `POST /timelapse` - Start/stop timelapse  
- `POST /toggle_camera` - Enable/disable stream
- `POST /set_rotation` - Rotate camera view
- `POST /set_stream_resolution` - Change resolution
- `GET /timelapse_status` - Get timelapse info

## Quick Start

```bash
cd /home/pi/repos/CameraControl
./setup.sh              # Install dependencies
source venv/bin/activate # Activate environment  
python app.py           # Start server
```

Access at: `http://[PI_IP]:5000`

---

This simplified version is perfect for basic camera control without additional hardware dependencies!