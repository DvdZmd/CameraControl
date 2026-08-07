from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()

# Tabla legacy conservada para no perder registros de instalaciones existentes.
class ErrorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    module = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    traceback = db.Column(db.Text, nullable=False)


class ApplicationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    level = db.Column(db.String(10), nullable=False, index=True)
    logger_name = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(255), nullable=True)
    function = db.Column(db.String(255), nullable=True)
    line_number = db.Column(db.Integer, nullable=True)
    exception_type = db.Column(db.String(255), nullable=True)
    traceback = db.Column(db.Text, nullable=True)
    request_id = db.Column(db.String(64), nullable=True, index=True)
    http_method = db.Column(db.String(10), nullable=True)
    request_path = db.Column(db.String(2048), nullable=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    def set_password(self, password):
        """
        Hash and store a user's password.

        Args:
            password: Plaintext password to hash before persistence.

        Returns:
            None
        """
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """
        Verify a plaintext password against the stored hash.

        Args:
            password: Plaintext password to validate.

        Returns:
            True when the password matches the stored hash, otherwise False.
        """
        return check_password_hash(self.password_hash, password)

class TimelapseConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    interval_minutes = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    is_running = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    interval_seconds = db.Column(db.Integer, nullable=False, default=10)
    auto_resume = db.Column(db.Boolean, nullable=False, default=True)
    save_path = db.Column(db.String(2048), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    stopped_at = db.Column(db.DateTime, nullable=True)
    last_capture_at = db.Column(db.DateTime, nullable=True)
    last_capture_path = db.Column(db.String(4096), nullable=True)
    capture_count = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text, nullable=True)


class SensorReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    temperature_air = db.Column(db.Float, nullable=False)
    humidity_air = db.Column(db.Float, nullable=False)
    temperature_soil = db.Column(db.Float, nullable=False)
    humidity_soil = db.Column(db.Float, nullable=False)
    # Reservados para capturas asociadas a timelapse. La telemetría periódica
    # ambiental no completa estas columnas.
    pan_pulse_us = db.Column(db.Integer, nullable=True)
    tilt_pulse_us = db.Column(db.Integer, nullable=True)


class CameraSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    camera_model = db.Column(db.String(255), nullable=True)
    max_width = db.Column(db.Integer, nullable=True)
    max_height = db.Column(db.Integer, nullable=True)
    af_supported = db.Column(db.Boolean, nullable=True)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    rotation = db.Column(db.Integer, nullable=False, default=0)
    pipeline_rotation = db.Column(db.Integer, nullable=False, default=0)
    display_rotation = db.Column(db.Integer, nullable=False, default=0)
    controls = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Esp32Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_pan_pulse = db.Column(db.Integer, nullable=True)
    custom_tilt_pulse = db.Column(db.Integer, nullable=True)
    speed_mode = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TuyaDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    tuya_name = db.Column(db.String(255), nullable=True)
    device_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    switch_code = db.Column(db.String(80), nullable=False, default="switch_1")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
