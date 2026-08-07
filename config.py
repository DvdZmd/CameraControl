# config.py
# Camera Control Configuration
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple


def _load_env_file() -> None:
    """Load environment variables from a .env file in the project root.

    Values already present in the process environment take precedence over the
    file contents, which makes local overrides work as expected.
    """
    env_paths = [Path(__file__).resolve().parent / ".env"]

    for env_path in env_paths:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_env_file()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_positive_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_positive_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _project_path_env(name: str, default: str) -> str:
    path = Path(os.environ.get(name, default)).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return str(path.resolve())

# === GLOBAL CONSTANTS (used by imports) ===
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
PROJECT_ROOT = Path(__file__).resolve().parent
TIMELAPSE_DIR = str((PROJECT_ROOT / "timelapse").resolve())

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
    level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    console_enabled: bool = field(default_factory=lambda: _env_bool("LOG_CONSOLE_ENABLED", True))
    console_level: str = field(default_factory=lambda: os.environ.get("LOG_CONSOLE_LEVEL", "INFO"))
    file_enabled: bool = field(default_factory=lambda: _env_bool("LOG_FILE_ENABLED", True))
    file_level: str = field(default_factory=lambda: os.environ.get("LOG_FILE_LEVEL", "ERROR"))
    file_path: str = field(
        default_factory=lambda: os.path.abspath(os.environ.get("LOG_FILE_PATH", "./logs/server.log"))
    )
    file_max_bytes: int = field(default_factory=lambda: _env_positive_int("LOG_FILE_MAX_BYTES", 10 * 1024 * 1024))
    file_backup_count: int = field(default_factory=lambda: _env_positive_int("LOG_FILE_BACKUP_COUNT", 5))
    database_enabled: bool = field(default_factory=lambda: _env_bool("LOG_DB_ENABLED", False))
    database_level: str = field(default_factory=lambda: os.environ.get("LOG_DB_LEVEL", "ERROR"))
    database_queue_size: int = field(default_factory=lambda: _env_positive_int("LOG_DB_QUEUE_SIZE", 1000))
    database_retention_days: int = field(default_factory=lambda: _env_positive_int("LOG_DB_RETENTION_DAYS", 30))
    database_max_rows: int = field(default_factory=lambda: _env_positive_int("LOG_DB_MAX_ROWS", 50000))
    werkzeug_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL_WERKZEUG", "INFO"))
    sqlalchemy_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL_SQLALCHEMY", "WARNING"))
    bleak_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL_BLEAK", "WARNING"))
    tuya_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL_TUYA", "WARNING"))

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
    timelapse_dir: str = field(
        default_factory=lambda: _project_path_env("TIMELAPSE_DIR", "timelapse")
    )
    default_interval_seconds: int = field(
        default_factory=lambda: _env_positive_int("TIMELAPSE_INTERVAL_SECONDS", 10)
    )
    auto_resume: bool = field(
        default_factory=lambda: _env_bool("TIMELAPSE_AUTO_RESUME", True)
    )

@dataclass
class SensorLoggingConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("SENSOR_LOG_ENABLED", True))
    interval_seconds: float = field(
        default_factory=lambda: _env_positive_float("SENSOR_LOG_INTERVAL_SECONDS", 60.0)
    )

# Combined AppConfig
@dataclass
class AppConfig:
    timezone_name: str = field(
        default_factory=lambda: os.environ.get(
            "APP_TIMEZONE", "America/Argentina/Buenos_Aires"
        )
    )
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    timelapse: TimelapseConfig = field(default_factory=TimelapseConfig)
    sensor_logging: SensorLoggingConfig = field(default_factory=SensorLoggingConfig)
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
