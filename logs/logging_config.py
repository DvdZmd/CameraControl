import logging
import os
from config import LOG_FILE_PATH, LOG_LEVEL

# Crear la carpeta si no existe
log_dir = os.path.dirname(LOG_FILE_PATH)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Crear logger
logger = logging.getLogger("CameraControl")
logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))  # default INFO

# Formato del log
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Handler de archivo
file_handler = logging.FileHandler(LOG_FILE_PATH)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Handler de consola (opcional, para desarrollo)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)