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

