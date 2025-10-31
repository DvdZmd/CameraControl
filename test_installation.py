#!/usr/bin/env python3
"""
Test script to verify CameraControl installation and dependencies
"""

def test_imports():
    """Test that all required modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        import flask
        print(f"✅ Flask {flask.__version__}")
    except ImportError as e:
        print(f"❌ Flask: {e}")
        return False
    
    try:
        import flask_sqlalchemy
        print(f"✅ Flask-SQLAlchemy {flask_sqlalchemy.__version__}")
    except ImportError as e:
        print(f"❌ Flask-SQLAlchemy: {e}")
        return False
    
    try:
        import cv2
        print(f"✅ OpenCV {cv2.__version__}")
    except ImportError as e:
        print(f"❌ OpenCV: {e}")
        return False
    
    try:
        import numpy
        print(f"✅ NumPy {numpy.__version__}")
    except ImportError as e:
        print(f"❌ NumPy: {e}")
        return False
    
    try:
        import picamera2
        print("✅ Picamera2 available")
    except ImportError as e:
        print(f"⚠️  Picamera2 not available (expected on non-Pi systems): {e}")
    
    return True

def test_config():
    """Test that configuration loads correctly"""
    print("\n⚙️  Testing configuration...")
    
    try:
        from config import (
            CAMERA_WIDTH, CAMERA_HEIGHT, FRAME_RATE, 
            AVAILABLE_RESOLUTIONS, LOG_FILE_PATH, TIMELAPSE_DIR
        )
        print("✅ Configuration constants loaded")
        print(f"   Camera: {CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {FRAME_RATE}fps")
        print(f"   Available resolutions: {len(AVAILABLE_RESOLUTIONS)} options")
        return True
    except ImportError as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_database_models():
    """Test that database models load correctly"""
    print("\n🗃️  Testing database models...")
    
    try:
        from database.models import db, TimelapseConfig, ErrorLog, User
        print("✅ Database models loaded")
        print("   - TimelapseConfig (for timelapse settings)")
        print("   - ErrorLog (for error tracking)")
        print("   - User (for future authentication)")
        return True
    except ImportError as e:
        print(f"❌ Database models error: {e}")
        return False

def test_camera_modules():
    """Test camera module imports"""
    print("\n📷 Testing camera modules...")
    
    try:
        from camera.timelapse import get_timelapse_config, is_timelapse_running
        print("✅ Timelapse module loaded")
    except ImportError as e:
        print(f"❌ Timelapse module error: {e}")
        return False
    
    try:
        from camera.picam import camera_available, get_camera_status
        status = get_camera_status()
        print(f"✅ Camera module loaded")
        print(f"   Camera available: {status['available']}")
        print(f"   Picamera2 object: {status['picam2']}")
        return True
    except Exception as e:
        print(f"❌ Camera module error: {e}")
        return False

def test_app_factory():
    """Test that Flask app can be created"""
    print("\n🏭 Testing application factory...")
    
    try:
        from app_factory import create_app
        app = create_app()
        print(f"✅ Flask app created successfully")
        print(f"   Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
        return True
    except Exception as e:
        print(f"❌ App factory error: {e}")
        return False

def main():
    print("🎥 CameraControl Installation Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_config, 
        test_database_models,
        test_camera_modules,
        test_app_factory
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Your installation looks good.")
        print("\n🚀 Next steps:")
        print("1. Ensure you're on a Raspberry Pi with camera enabled")
        print("2. Run: python app.py")
        print("3. Access: http://localhost:5000")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")
        print("   Try running: pip install -r requirements.txt")

if __name__ == "__main__":
    main()