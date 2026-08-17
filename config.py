# config.py
# Camera Control Configuration
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
INSTANCE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


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
        path = PROJECT_ROOT / path
    return str(path.resolve())


def _resolved_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class InstanceConfig:
    """Identidad y almacenamiento aislado de una instalación física."""

    name: str
    data_dir: Path
    database_path: Path
    timelapse_dir: Path
    log_path: Path

    @classmethod
    def from_env(cls) -> "InstanceConfig":
        name = os.environ.get("CAMERACONTROL_INSTANCE", "default").strip()
        if not INSTANCE_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "CAMERACONTROL_INSTANCE debe comenzar con letra minúscula o "
                "número y contener sólo minúsculas, números, guion o guion bajo"
            )

        configured_data_dir = os.environ.get("CAMERACONTROL_DATA_DIR") or None
        isolated = name != "default" or configured_data_dir is not None
        if isolated:
            data_root = _resolved_project_path(configured_data_dir or "data") / name
            default_database = data_root / "app.db"
            default_timelapse = data_root / "timelapse"
            default_log = data_root / "logs" / "server.log"
        else:
            data_root = PROJECT_ROOT
            default_database = PROJECT_ROOT / "database" / "app.db"
            default_timelapse = PROJECT_ROOT / "timelapse"
            default_log = PROJECT_ROOT / "logs" / "server.log"

        database_path = _resolved_project_path(
            os.environ.get("DATABASE_PATH") or default_database
        )
        timelapse_dir = _resolved_project_path(
            os.environ.get("TIMELAPSE_DIR") or default_timelapse
        )
        log_path = _resolved_project_path(
            os.environ.get("LOG_FILE_PATH") or default_log
        )
        return cls(
            name=name,
            data_dir=data_root.resolve(),
            database_path=database_path,
            timelapse_dir=timelapse_dir,
            log_path=log_path,
        )

    def ensure_directories(self) -> None:
        """Crea sólo los directorios requeridos por esta instancia."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.timelapse_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class LoggingConfig:
    level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    console_enabled: bool = field(
        default_factory=lambda: _env_bool("LOG_CONSOLE_ENABLED", True)
    )
    console_level: str = field(
        default_factory=lambda: os.environ.get("LOG_CONSOLE_LEVEL", "INFO")
    )
    file_enabled: bool = field(default_factory=lambda: _env_bool("LOG_FILE_ENABLED", True))
    file_level: str = field(default_factory=lambda: os.environ.get("LOG_FILE_LEVEL", "ERROR"))
    file_path: str = field(
        default_factory=lambda: os.path.abspath(
            os.environ.get("LOG_FILE_PATH", "./logs/server.log")
        )
    )
    file_max_bytes: int = field(
        default_factory=lambda: _env_positive_int(
            "LOG_FILE_MAX_BYTES", 10 * 1024 * 1024
        )
    )
    file_backup_count: int = field(
        default_factory=lambda: _env_positive_int("LOG_FILE_BACKUP_COUNT", 5)
    )
    database_enabled: bool = field(default_factory=lambda: _env_bool("LOG_DB_ENABLED", False))
    database_level: str = field(
        default_factory=lambda: os.environ.get("LOG_DB_LEVEL", "ERROR")
    )
    database_queue_size: int = field(
        default_factory=lambda: _env_positive_int("LOG_DB_QUEUE_SIZE", 1000)
    )
    database_retention_days: int = field(
        default_factory=lambda: _env_positive_int("LOG_DB_RETENTION_DAYS", 30)
    )
    database_max_rows: int = field(
        default_factory=lambda: _env_positive_int("LOG_DB_MAX_ROWS", 50000)
    )
    werkzeug_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL_WERKZEUG", "INFO")
    )
    sqlalchemy_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL_SQLALCHEMY", "WARNING")
    )
    bleak_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL_BLEAK", "WARNING")
    )
    tuya_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL_TUYA", "WARNING")
    )


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
    enabled: bool = field(
        default_factory=lambda: _env_bool("SENSOR_LOG_ENABLED", True)
    )
    interval_seconds: float = field(
        default_factory=lambda: _env_positive_float("SENSOR_LOG_INTERVAL_SECONDS", 60.0)
    )


@dataclass
class TuyaConfig:
    """Configuración para la integración con Tuya Smart Life."""

    api_key: str = field(
        default_factory=lambda: os.environ.get("TUYA_API_KEY", ""),
        repr=False,
    )
    api_secret: str = field(
        default_factory=lambda: os.environ.get("TUYA_API_SECRET", ""),
        repr=False,
    )
    api_endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "TUYA_API_ENDPOINT", "https://openapi.tuyaus.com"
        )
    )
    device_id: str = field(
        default_factory=lambda: os.environ.get("TUYA_DEVICE_ID", ""),
        repr=False,
    )
    username: str = field(
        default_factory=lambda: os.environ.get("TUYA_USERNAME", ""),
        repr=False,
    )
    password: str = field(
        default_factory=lambda: os.environ.get("TUYA_PASSWORD", ""),
        repr=False,
    )
    country_code: str = field(
        default_factory=lambda: os.environ.get("TUYA_COUNTRY_CODE", "")
    )
    schema: str = field(
        default_factory=lambda: os.environ.get("TUYA_SCHEMA", "tuya")
    )


@dataclass
class AppConfig:
    """Configuración activa de servicios al crear la aplicación Flask."""

    instance: InstanceConfig = field(default_factory=InstanceConfig.from_env)
    timezone_name: str = field(
        default_factory=lambda: os.environ.get(
            "APP_TIMEZONE", "America/Argentina/Buenos_Aires"
        )
    )
    logging: LoggingConfig | None = None
    timelapse: TimelapseConfig | None = None
    sensor_logging: SensorLoggingConfig = field(default_factory=SensorLoggingConfig)
    tuya: TuyaConfig = field(default_factory=TuyaConfig)

    def __post_init__(self) -> None:
        if self.logging is None:
            self.logging = LoggingConfig(file_path=str(self.instance.log_path))
        if self.timelapse is None:
            self.timelapse = TimelapseConfig(
                timelapse_dir=str(self.instance.timelapse_dir)
            )
