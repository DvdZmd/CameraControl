from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()

#TODO create SystemLog model to log system events
class ErrorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    module = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    traceback = db.Column(db.Text, nullable=False)

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
    device_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    switch_code = db.Column(db.String(80), nullable=False, default="switch_1")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
