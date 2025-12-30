"""
Camera Routes - Main Blueprint Registration
This module imports and registers all camera-related blueprints.

The routes have been split into three modules for better organization:
- camera_basic.py: Stream, capture, status, timelapse (basic operations)
- camera_controls.py: Manual controls, presets, focus, exposure
- camera_advanced.py: Resolution, modes, white balance, ROI/zoom/pan

Usage in app_factory.py:
    from routes.camera_routes import camera_bp, register_camera_blueprints
    app.register_blueprint(camera_bp)
    register_camera_blueprints(app)
"""

from flask import Blueprint
from routes.camera_basic import camera_basic_bp
from routes.camera_controls import camera_controls_bp
from routes.camera_advanced import camera_advanced_bp

# Main blueprint for backward compatibility
camera_bp = Blueprint('camera', __name__)


def register_camera_blueprints(app):
    """
    Register all camera-related blueprints to the Flask app.
    
    This function should be called from your Flask app factory after
    registering the main camera_bp blueprint.
    
    Args:
        app: Flask application instance
    """
    app.register_blueprint(camera_basic_bp)
    app.register_blueprint(camera_controls_bp)
    app.register_blueprint(camera_advanced_bp)
