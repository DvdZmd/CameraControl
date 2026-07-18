# config.py
# Camera Control Configuration
import os
from dataclasses import dataclass, field
from typing import List, Tuple

# === GLOBAL CONSTANTS (used by imports) ===
# Logging
LOG_FILE_PATH = os.path.abspath("./logs/server.log")
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Camera settings 
CAMERA_WIDTH = 1640
CAMERA_HEIGHT = 1232
FRAME_RATE = 30
NOISE_REDUCTION_MODE = 2

# Server-side zoom and pan (ROI - Region of Interest)
# ROI format: (x, y, width, height) as fractions (0.0 to 1.0)
CAMERA_ROI = (0.0, 0.0, 1.0, 1.0)  # Full frame by default

# Extended camera controls (defaults matching rpicam-hello exactly)
BRIGHTNESS = 0.0  # Range: -1.0 to 1.0
CONTRAST = 1.0    # Range: 0.0 to 32.0
SATURATION = 1.0  # Range: 0.0 to 32.0
SHARPNESS = 1.0   # Range: 0.0 to 16.0
EXPOSURE_TIME = None  # Auto exposure
ANALOGUE_GAIN = 1.0   # Range: 1.0 to 16.0
DIGITAL_GAIN = 1.0    # Range: 1.0 to 64.0
AWB_MODE = 0          # Auto White Balance: 0=auto
LENS_POSITION = None  # Manual focus
AF_MODE = 2           # Autofocus mode: 0=manual, 1=auto, 2=continuous

# Timelapse folder
TIMELAPSE_DIR = os.path.abspath("./timelapse")

# Available camera resolutions (width, height)
AVAILABLE_RESOLUTIONS = [
    (640, 480),
    (800, 600),
    (1280, 720),
    (1920, 1080),
    (2592, 1944),
]

# === END OF GLOBAL CONSTANTS ===

# === DATACLASS CONFIGURATIONS ===

@dataclass
class LoggingConfig:
    log_file_path: str = os.path.abspath("./logs/server.log")
    log_level: str = "INFO"

@dataclass
class CameraConfig:
    # Basic settings (matching rpicam-hello defaults exactly)
    width: int = 0
    height: int = 0
    frame_rate: int = 30
    noise_reduction_mode: int = 2
    # Server-side zoom and pan
    roi: tuple = (0.0, 0.0, 1.0, 1.0)  # (x, y, width, height) as fractions
    available_resolutions: List[Tuple[int, int]] = field(default_factory=lambda: [
        (640, 480),
        (800, 600),
        (1280, 720),
        (1920, 1080),
        (2592, 1944),
    ])
    
    # Extended camera controls (matching rpicam-hello defaults exactly)
    brightness: float = 0.0      # Range: -1.0 to 1.0
    contrast: float = 1.0        # Range: 0.0 to 32.0
    saturation: float = 1.0      # Range: 0.0 to 32.0
    sharpness: float = 1.0       # Range: 0.0 to 16.0
    exposure_time: int = None    # Microseconds, None for auto
    analogue_gain: float = 1.0   # Range: 1.0 to 16.0
    digital_gain: float = 1.0    # Range: 1.0 to 64.0
    awb_mode: int = 0            # Auto White Balance: 0=auto
    lens_position: float = None  # Manual focus: 0.0 to 32.0, None for auto
    af_mode: int = 2             # Autofocus: 0=manual, 1=auto, 2=continuous

@dataclass
class TimelapseConfig:
    timelapse_dir: str = os.path.abspath("./timelapse")

# Combined AppConfig
@dataclass
class AppConfig:
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    timelapse: TimelapseConfig = field(default_factory=TimelapseConfig)
    tuya: 'TuyaConfig' = field(default_factory=lambda: TuyaConfig())

@dataclass
class TuyaConfig:
    """Configuración para la integración con Tuya Smart Life."""
    # IMPORTANT: Do NOT store secrets in source. Provide values via environment variables
    api_key: str = os.environ.get("TUYA_API_KEY", "")  # Tu Access ID de la Tuya IoT Platform
    api_secret: str = os.environ.get("TUYA_API_SECRET", "")  # Tu Access Secret de la Tuya IoT Platform
    api_endpoint: str = os.environ.get("TUYA_API_ENDPOINT", "https://openapi.tuyaus.com")  # Cambia a tu región (ej. https://openapi.tuyaeu.com para Europa)
    device_id: str = os.environ.get("TUYA_DEVICE_ID", "")  # El ID de tu dispositivo (el enchufe)
    username: str = os.environ.get("TUYA_USERNAME", "")  # Tu usuario de Tuya Smart Life / email
    password: str = os.environ.get("TUYA_PASSWORD", "")  # Tu contraseña de Tuya Smart Life
    country_code: str = os.environ.get("TUYA_COUNTRY_CODE", "")  # Código de país para Smart Home login, p.ej. "34" para España
    schema: str = os.environ.get("TUYA_SCHEMA", "tuya")  # Esquema de la app Tuya/Smart Life (Smart Home login)
