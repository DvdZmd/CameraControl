# camera/camera_utils.py
"""
Utilidades para configuración avanzada de la cámara
Proporciona funciones helper para configurar aspectos específicos de la cámara
"""

from typing import Dict, Any, List, Tuple, Optional
from logs.logging_config import logger


class CameraPresets:
    """Presets predefinidos para diferentes escenarios de cámara"""
    
    # Preset que replica exactamente rpicam-hello defaults
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


class CameraControlLimits:
    """Límites y rangos para controles de cámara"""
    
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
    Valida y ajusta valores de control dentro de rangos permitidos
    
    Args:
        control_name: Nombre del control
        value: Valor a validar
        
    Returns:
        Tuple[bool, Any]: (is_valid, adjusted_value)
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
    
    # For other controls, return as-is
    return True, value


def apply_preset(camera_controller, preset_name: str) -> bool:
    """
    Aplica un preset predefinido a la cámara
    
    Args:
        camera_controller: Instancia del controlador de cámara
        preset_name: Nombre del preset ("daylight", "indoor", etc.)
        
    Returns:
        bool: True si se aplicó correctamente
    """
    presets = CameraPresets()
    
    preset_map = {
        "rpicam_hello": presets.RPICAM_HELLO_DEFAULT,
        "default": presets.RPICAM_HELLO_DEFAULT,  # Alias
        "daylight": presets.DAYLIGHT,
        "indoor": presets.INDOOR,
        "low_light": presets.LOW_LIGHT,
        "high_contrast": presets.HIGH_CONTRAST,
        "timelapse": presets.TIMELAPSE
    }
    
    if preset_name.lower() not in preset_map:
        logger.warning(f"[Camera] Preset '{preset_name}' not found")
        return False
    
    preset_controls = preset_map[preset_name.lower()]
    
    # Validate all controls before applying
    validated_controls = {}
    for control, value in preset_controls.items():
        is_valid, adjusted_value = validate_control_value(control, value)
        if is_valid:
            validated_controls[control] = adjusted_value
        else:
            logger.warning(f"[Camera] Invalid value for {control}: {value}")
    
    if validated_controls:
        success = camera_controller.update_multiple_controls(validated_controls)
        if success:
            logger.info(f"[Camera] Applied preset: {preset_name}")
        return success
    
    return False


def create_custom_preset(controls: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea un preset personalizado validando todos los controles
    
    Args:
        controls: Diccionario de controles y valores
        
    Returns:
        Dict con controles validados
    """
    validated_preset = {}
    
    for control, value in controls.items():
        is_valid, adjusted_value = validate_control_value(control, value)
        if is_valid:
            validated_preset[control] = adjusted_value
        else:
            logger.warning(f"[Camera] Invalid control in preset: {control}={value}")
    
    return validated_preset


def get_focus_distance_estimate(lens_position: float) -> str:
    """
    Estima la distancia de enfoque basada en la posición del lente
    
    Args:
        lens_position: Posición del lente (0.0 a 32.0)
        
    Returns:
        str: Descripción estimada de la distancia
    """
    if lens_position <= 1.0:
        return "Infinity (Infinito)"
    elif lens_position <= 5.0:
        return "Far distance (> 10m)"
    elif lens_position <= 10.0:
        return "Medium distance (2-10m)"
    elif lens_position <= 20.0:
        return "Close distance (0.5-2m)"
    else:
        return "Macro distance (< 0.5m)"


def calculate_optimal_exposure(scene_type: str) -> Optional[int]:
    """
    Calcula tiempo de exposición óptimo según el tipo de escena
    
    Args:
        scene_type: Tipo de escena ("daylight", "indoor", "low_light", "night")
        
    Returns:
        Tiempo de exposición en microsegundos, o None para auto
    """
    exposure_map = {
        "daylight": 5000,      # 5ms
        "indoor": 15000,       # 15ms  
        "low_light": 50000,    # 50ms
        "night": 100000,       # 100ms
        "auto": None
    }
    
    return exposure_map.get(scene_type.lower())


def generate_focus_steps(start: float = 0.0, end: float = 32.0, steps: int = 20) -> List[float]:
    """
    Genera una lista de pasos de enfoque para barrido automático
    
    Args:
        start: Posición inicial del lente
        end: Posición final del lente  
        steps: Número de pasos
        
    Returns:
        Lista de posiciones de enfoque
    """
    if steps <= 1:
        return [start]
    
    step_size = (end - start) / (steps - 1)
    return [start + i * step_size for i in range(steps)]


def detect_and_fix_blue_tint(camera_controller) -> bool:
    """
    Detecta y corrige automáticamente el tinte azul común en cámaras Raspberry Pi
    
    Args:
        camera_controller: Instancia del controlador de cámara
        
    Returns:
        bool: True si se aplicó una corrección
    """
    if not camera_controller.picam2:
        return False
    
    try:
        # Capturar una muestra pequeña para análisis
        sample = camera_controller.picam2.capture_array()
        
        # Analizar balance de color (promedio de canales RGB)
        import numpy as np
        
        # Convertir de BGR a RGB si es necesario
        if len(sample.shape) == 3 and sample.shape[2] == 3:
            # Calcular promedios por canal
            r_avg = np.mean(sample[:, :, 0])  # Red
            g_avg = np.mean(sample[:, :, 1])  # Green  
            b_avg = np.mean(sample[:, :, 2])  # Blue
            
            # Detectar tinte azul (canal azul dominante)
            blue_ratio = b_avg / (r_avg + g_avg + b_avg)
            
            logger.info(f"[AWB] Color analysis - R:{r_avg:.1f} G:{g_avg:.1f} B:{b_avg:.1f}, Blue ratio: {blue_ratio:.3f}")
            
            # Si el azul es más del 40% del total, hay tinte azul
            if blue_ratio > 0.4:
                logger.warning("[AWB] Blue tint detected, applying correction...")
                
                # Aplicar corrección según la severidad
                if blue_ratio > 0.5:
                    # Tinte azul severo - usar modo daylight
                    correction = {"AwbMode": 5, "Saturation": 0.8}
                    logger.info("[AWB] Applying strong correction (Daylight mode)")
                else:
                    # Tinte azul moderado - usar auto con saturación reducida
                    correction = {"AwbMode": 0, "Saturation": 0.9}
                    logger.info("[AWB] Applying moderate correction (Auto mode)")
                
                success = camera_controller.update_multiple_controls(correction)
                if success:
                    logger.info("[AWB] Blue tint correction applied successfully")
                    return True
                else:
                    logger.error("[AWB] Failed to apply blue tint correction")
                    return False
            else:
                logger.info("[AWB] No blue tint detected, colors look balanced")
                return False
                
    except Exception as e:
        logger.exception("[AWB] Error during blue tint detection")
        return False


def auto_white_balance_by_environment() -> int:
    """
    Intenta detectar automáticamente el mejor modo AWB según el entorno
    
    Returns:
        int: Modo AWB recomendado
    """
    import time
    
    # Obtener hora actual para detectar condiciones de luz
    current_hour = time.localtime().tm_hour
    
    if 6 <= current_hour <= 18:
        # Día - probablemente luz natural
        return 5  # Daylight
    elif 18 < current_hour <= 22:
        # Tarde/noche temprana - probablemente luz artificial
        return 1  # Incandescent
    else:
        # Noche - dejar en auto
        return 0  # Auto


def create_balanced_preset() -> Dict[str, Any]:
    """
    Crea un preset balanceado basado en rpicam-hello defaults
    
    Returns:
        Dict con configuraciones balanceadas
    """

    balanced = {
        "Brightness": 0.0,
        "Contrast": 1.0,
        "Saturation": 1.0,
        "Sharpness": 1.0,
        "AwbMode": 0,
        "AnalogueGain": 1.0,
        "DigitalGain": 1.0
    }
    
    logger.info("[AWB] Created balanced preset using rpicam-hello defaults")
    return balanced


def get_control_info() -> Dict[str, Dict[str, Any]]:
    """
    Retorna información detallada sobre todos los controles disponibles
    
    Returns:
        Dict con información de cada control (rangos, descripción, etc.)
    """
    limits = CameraControlLimits()
    
    return {
        "Brightness": {
            "range": limits.BRIGHTNESS,
            "type": "float",
            "description": "Ajusta el brillo de la imagen (-1.0 = muy oscuro, 1.0 = muy brillante)",
            "default": 0.0
        },
        "Contrast": {
            "range": limits.CONTRAST,
            "type": "float", 
            "description": "Ajusta el contraste de la imagen (0.0 = sin contraste, 2.0+ = alto contraste)",
            "default": 1.0
        },
        "Saturation": {
            "range": limits.SATURATION,
            "type": "float",
            "description": "Ajusta la saturación de color (0.0 = escala de grises, 2.0+ = muy saturado)",
            "default": 1.0
        },
        "Sharpness": {
            "range": limits.SHARPNESS, 
            "type": "float",
            "description": "Ajusta la nitidez de la imagen (0.0 = muy suave, 2.0+ = muy nítido)",
            "default": 1.0
        },
        "AnalogueGain": {
            "range": limits.ANALOGUE_GAIN,
            "type": "float",
            "description": "Ganancia analógica del sensor (1.0 = sin ganancia, valores altos = más sensibilidad/ruido)",
            "default": 1.0
        },
        "DigitalGain": {
            "range": limits.DIGITAL_GAIN,
            "type": "float", 
            "description": "Ganancia digital (1.0 = sin ganancia, valores altos = más brillo pero más ruido)",
            "default": 1.0
        },
        "LensPosition": {
            "range": limits.LENS_POSITION,
            "type": "float",
            "description": "Posición manual del enfoque (0.0 = infinito, 32.0 = muy cerca)",
            "default": None
        },
        "ExposureTime": {
            "range": (limits.EXPOSURE_TIME_MIN, limits.EXPOSURE_TIME_MAX),
            "type": "int",
            "description": "Tiempo de exposición en microsegundos (None = automático)",
            "default": None
        },
        "AwbMode": {
            "options": limits.AWB_MODES,
            "type": "int",
            "description": "Modo de balance de blancos automático",
            "default": 0
        },
        "AfMode": {
            "options": limits.AF_MODES,
            "type": "int", 
            "description": "Modo de enfoque automático",
            "default": 2
        }
    }