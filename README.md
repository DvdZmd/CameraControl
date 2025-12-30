# 🎥 Raspberry Pi Camera Control

A lightweight Python Flask web application focused on Raspberry Pi camera streaming and control. This project provides essential camera functionality without additional hardware dependencies like servos, I2C devices, or Bluetooth modules.

## 🚀 Features

- **Live Camera Streaming**: Real-time MJPEG video feed via web browser
- **Timelapse Photography**: Automated image capture with configurable intervals
- **Image Capture**: High-quality photo capture at multiple resolutions
- **Camera Controls**: 
  - Multiple resolution options (640x480 to 2592x1944)
  - Camera rotation (0°, 90°, 180°, 270°)
  - Stream enable/disable toggle
- **Simple Configuration**: Easy-to-modify camera settings
- **Database Integration**: Configuration persistence with SQLAlchemy
- **Comprehensive Logging**: File and database error logging
- **RESTful API**: Clean API endpoints for all camera operations

## 🛠️ Hardware Requirements

- Raspberry Pi (3B+, 4, or newer recommended)
- Raspberry Pi Camera Module (v1, v2, or HQ Camera)
- MicroSD card (16GB+ recommended)
- Network connection (WiFi or Ethernet)

## 📦 Installation

### Quick Setup (Recommended)

```bash
# Clone or navigate to the project directory
cd /path/to/CameraControl

# Run the automated setup script
./setup.sh

# Activate the virtual environment
source venv/bin/activate

# Start the application
python app.py
```

### Manual Installation

1. **Update System Packages**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Install System Dependencies**
```bash
sudo apt install -y python3-dev python3-pip python3-venv libcamera-dev \
    libcamera-apps python3-libcamera python3-kms++ libatlas-base-dev \
    libjpeg-dev libpng-dev libtiff-dev libavcodec-dev libavformat-dev \
    libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev \
    libcanberra-gtk-module libcanberra-gtk3-module ffmpeg cmake
```

3. **Enable Camera Interface**
```bash
# Add to /boot/config.txt if not present
echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
sudo reboot  # Required after enabling camera
```

4. **Create Python Environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

5. **Create Required Directories**
```bash
mkdir -p /home/pi/Desktop/logs
mkdir -p /home/pi/Desktop/timelapse
mkdir -p Pictures
```

## 🚀 Usage

### Starting the Server

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Start the Flask application
python app.py
```

The server will start on `http://0.0.0.0:5000` and be accessible from:
- Local Pi: `http://localhost:5000`
- Network devices: `http://[PI_IP_ADDRESS]:5000`

### API Endpoints

#### Camera Streaming
- `GET /video_feed` - Live camera stream (MJPEG)
- `POST /toggle_camera` - Enable/disable camera stream
- `POST /set_rotation` - Set camera rotation (0, 90, 180, 270 degrees)

#### Image Capture
- `GET /capture_image?width=1280&height=720` - Capture and download image

#### Timelapse Control
- `GET /timelapse_status` - Get current timelapse configuration
- `POST /timelapse` - Start/stop timelapse

**Timelapse Start Example:**
```json
{
    "action": "start",
    "interval_minutes": 5,
    "width": 1280,
    "height": 720
}
```

**Timelapse Stop Example:**
```json
{
    "action": "stop"
}
```

**Resolution Change Example:**
```json
{
    "resolution": "1280x720"
}
```

### Available Resolutions
- 640x480 (VGA)
- 800x600 (SVGA)  
- 1280x720 (HD)
- 1920x1080 (Full HD)
- 2592x1944 (Max - depends on camera model)

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
