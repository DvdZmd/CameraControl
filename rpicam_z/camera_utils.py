from enum import auto
from typing import Dict, Any, List, Tuple, Optional
from logs.logging_config import logger


class CameraPresets:
    """Predefined presets for different camera scenarios."""
    
    # Preset that exactly replicates rpicam-hello defaults
    RPICAM_HELLO_DEFAULT = {
        "Brightness": 0.0,
        "Contrast": 1.0,
        "Saturation": 1.0,
        "Sharpness": 1.0,
        "AwbMode": 0,
        "AnalogueGain": 1.0
    }
    
    DAYLIGHT = {
        "Brightness": 0.0,
        "Contrast": 1.2,
        "Saturation": 1.1,
        "Sharpness": 1.2,
        "AwbMode": 5,
        "AnalogueGain": 1.0
    }
    
    INDOOR = {
        "Brightness": 0.1,
        "Contrast": 1.1,
        "Saturation": 1.0,
        "Sharpness": 1.0,
        "AwbMode": 1,
        "AnalogueGain": 2.0
    }
    
    LOW_LIGHT = {
        "Brightness": 0.2,
        "Contrast": 0.9,
        "Saturation": 0.8,
        "Sharpness": 0.8,
        "AwbMode": 0,
        "AnalogueGain": 4.0,
        "DigitalGain": 2.0
    }
    
    HIGH_CONTRAST = {
        "Brightness": 0.0,
        "Contrast": 2.0,
        "Saturation": 1.3,
        "Sharpness": 1.5,
        "AwbMode": 0
    }
    
    TIMELAPSE = {
        "Brightness": 0.0,
        "Contrast": 1.0,
        "Saturation": 1.0,
        "Sharpness": 1.0,
        "AfMode": 2,
        "AwbMode": 0
    }
    
    NEUTRAL_WARM = {
        "Brightness": 0.0,
        "Contrast": 1.0,
        "Saturation": 0.9,
        "Sharpness": 1.0,
        "AwbMode": 5,
        "AnalogueGain": 1.0
    }
    
    LED_LIGHTING = {
        "Brightness": 0.0,
        "Contrast": 1.1,
        "Saturation": 1.0,
        "Sharpness": 1.0,
        "AwbMode": 4,
        "AnalogueGain": 1.5
    }

    LUNAR_PHOTOGRAPHY = {
        "AeEnable": False,      # Crucial to avoid the white "blown-out patch"
        "AnalogueGain": 1.0,    # Minimum ISO for sharpness
        "ExposureTime": 10000,  # Initial 10ms, adjust according to telescope
        "Brightness": 0.0,
        "Contrast": 1.5,        # Enhances crater relief
        "AfMode": 0             # Manual focus for telescope stability
    }


class CameraControlLimits:
    """Limits and ranges for camera controls."""
    
    BRIGHTNESS = (-1.0, 1.0)
    CONTRAST = (0.0, 32.0)
    SATURATION = (0.0, 32.0)
    SHARPNESS = (0.0, 16.0)
    ANALOGUE_GAIN = (1.0, 10.666667)
    DIGITAL_GAIN = (1.0, 64.0)
    LENS_POSITION = (0.0, 32.0)  # 0.0 = infinity, 32.0 = closest
    
    # Exposure time in microseconds
    EXPOSURE_TIME_MIN = 75
    EXPOSURE_TIME_MAX = 1238765  # ~1.24s
    
    # AWB modes
    AWB_MODES = {
        0: "Auto",
        1: "Incandescent", 
        2: "Tungsten",
        3: "Fluorescent",
        4: "Indoor",
        5: "Daylight",
        6: "Cloudy",
        7: "Custom"
    }

    AE_MODES = {
        True: "On",
        False: "Off"
    }
    
    # Exposure Value compensation
    EXPOSURE_VALUE = (-8.0, 8.0)  # EV compensation range
    
    # AF modes  
    AF_MODES = {
        0: "Manual",
        1: "Auto",
        2: "Continuous"
    }


def validate_control_value(control_name: str, value: Any) -> Tuple[bool, Any]:
    """
    Validate and normalize a camera control value.

    The function clamps numeric controls to supported ranges and validates
    enumerated controls against known camera modes. Exposure time values are
    interpreted in microseconds.

    Args:
        control_name: Camera control identifier.
        value: Proposed control value to validate.

    Returns:
        A tuple containing a validity flag and the normalized value that should
        be applied.
    """
    limits = CameraControlLimits()
    
    if control_name == "Brightness":
        min_val, max_val = limits.BRIGHTNESS
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "Contrast":
        min_val, max_val = limits.CONTRAST
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "Saturation":
        min_val, max_val = limits.SATURATION
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "Sharpness":
        min_val, max_val = limits.SHARPNESS
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "AnalogueGain":
        min_val, max_val = limits.ANALOGUE_GAIN
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "DigitalGain":
        min_val, max_val = limits.DIGITAL_GAIN
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "LensPosition":
        min_val, max_val = limits.LENS_POSITION
        adjusted = max(min_val, min(max_val, float(value)))
        return True, adjusted
        
    elif control_name == "ExposureTime":
        if value is None:
            return True, None  # Auto exposure
        adjusted = max(limits.EXPOSURE_TIME_MIN, 
                      min(limits.EXPOSURE_TIME_MAX, int(value)))
        return True, adjusted
        
    elif control_name == "AwbMode":
        if int(value) in limits.AWB_MODES:
            return True, int(value)
        return False, 0
        
    elif control_name == "AfMode":
        if int(value) in limits.AF_MODES:
            return True, int(value)
        return False, 2
    
    elif control_name == "AeEnable":
        return True, bool(value)
    
    # For other controls, return as-is
    return True, value


def get_control_info() -> Dict[str, Dict[str, Any]]:
    """
    Describe the supported camera controls for API consumers.

    Returns:
        A mapping of control names to metadata such as range, option set,
        default value, and human-readable description.
    """
    limits = CameraControlLimits()
    
    return {
        "Brightness": {
            "range": limits.BRIGHTNESS,
            "type": "float",
            "description": "Adjust image brightness (-1.0 = very dark, 1.0 = very bright)",
            "default": 0.0
        },
        "Contrast": {
            "range": limits.CONTRAST,
            "type": "float", 
            "description": "Adjust image contrast (0.0 = no contrast, 2.0+ = high contrast)",
            "default": 1.0
        },
        "Saturation": {
            "range": limits.SATURATION,
            "type": "float",
            "description": "Adjust color saturation (0.0 = grayscale, 2.0+ = highly saturated)",
            "default": 1.0
        },
        "Sharpness": {
            "range": limits.SHARPNESS, 
            "type": "float",
            "description": "Adjust image sharpness (0.0 = very soft, 2.0+ = very sharp)",
            "default": 1.0
        },
        "AnalogueGain": {
            "range": limits.ANALOGUE_GAIN,
            "type": "float",
            "description": "Sensor analog gain (1.0 = no gain, higher values = more sensitivity/noise)",
            "default": 1.0
        },
        "DigitalGain": {
            "range": limits.DIGITAL_GAIN,
            "type": "float", 
            "description": "Digital gain (1.0 = no gain, higher values = more brightness but more noise)",
            "default": 1.0
        },
        "LensPosition": {
            "range": limits.LENS_POSITION,
            "type": "float",
            "description": "Manual focus position (0.0 = infinity, 32.0 = very close)",
            "default": None
        },
        "ExposureTime": {
            "range": (limits.EXPOSURE_TIME_MIN, limits.EXPOSURE_TIME_MAX),
            "type": "int",
            "description": "Exposure time in microseconds (None = automatic)",
            "default": None
        },
        "AwbMode": {
            "options": limits.AWB_MODES,
            "type": "int",
            "description": "Automatic white balance mode",
            "default": 0
        },
        "AfMode": {
            "options": limits.AF_MODES,
            "type": "int", 
            "description": "Autofocus mode",
            "default": 2
        }
    }
