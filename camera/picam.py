from picamera2 import Picamera2, Preview
from config import (
    FRAME_RATE, NOISE_REDUCTION_MODE, CAMERA_WIDTH, CAMERA_HEIGHT,
    BRIGHTNESS, CONTRAST, SATURATION, SHARPNESS, EXPOSURE_TIME,
    ANALOGUE_GAIN, DIGITAL_GAIN, AWB_MODE, LENS_POSITION, AF_MODE, CAMERA_ROI
)
from logs.logging_config import logger
import time
from typing import Dict, Any, Optional

class CameraController:
    def __init__(self):
        self.picam2 = None
        self.video_config = None
        self.still_config = None
        self.current_controls = {}
        self.available_controls = {}
        # Handle rpicam-hello compatible resolution (0,0 = sensor default)
        if CAMERA_WIDTH == 0 and CAMERA_HEIGHT == 0:
            self.current_resolution = None  # Let Picamera2 use sensor default
        else:
            self.current_resolution = (CAMERA_WIDTH, CAMERA_HEIGHT)
        self.is_still_mode = False
        # Server-side zoom and pan (ROI)
        self.current_roi = CAMERA_ROI  # (x, y, width, height) as fractions
        
        self._initialize_camera()
    
    def _initialize_camera(self):
        """Initialize the camera with default settings"""
        try:
            self.picam2 = Picamera2()
            self.available_controls = self.picam2.camera_controls
            
            # Build initial controls dictionary
            self.current_controls = self._build_controls()
            
            # Create and configure camera
            if self.current_resolution is None:
                # Use sensor defaults (rpicam-hello behavior)
                self.video_config = self.picam2.create_video_configuration(
                    controls=self.current_controls
                )
                self.still_config = self.picam2.create_still_configuration(
                    controls=self.current_controls
                )
            else:
                # Use specified resolution
                self.video_config = self.picam2.create_video_configuration(
                    main={"size": self.current_resolution},
                    controls=self.current_controls
                )
                self.still_config = self.picam2.create_still_configuration(
                    main={"size": self.current_resolution},
                    controls=self.current_controls
                )
            
            self.picam2.configure(self.video_config)
            self.picam2.start()
            
            logger.info("[Camera] Cámara iniciada correctamente con configuraciones extendidas.")
            logger.info(f"[Camera] Controles aplicados: {self.current_controls}")
            
            # Initialize ROI (server-side zoom/pan)
            if self.current_roi != (0.0, 0.0, 1.0, 1.0):
                # Apply non-default ROI
                x, y, width, height = self.current_roi
                self.set_roi(x, y, width, height)
                logger.info(f"[Camera] ROI initialized: {self.current_roi}")
            
            # Aplicar corrección automática del tinte azul después de un breve período
            self._schedule_auto_correction()
            
        except Exception as e:
            logger.exception("[Camera] No se pudo iniciar la cámara")
            self.picam2 = None
            self.video_config = None
    
    def _schedule_auto_correction(self):
        """Programa la corrección automática del tinte azul"""
        import threading
        import time
        
        def delayed_correction():
            try:
                # Esperar 2 segundos para que la cámara se estabilice
                time.sleep(2)
                
                from camera.camera_utils import detect_and_fix_blue_tint
                success = detect_and_fix_blue_tint(self)
                
                if success:
                    logger.info("[Camera] Auto-correction applied for better color balance")
                else:
                    logger.info("[Camera] No auto-correction needed, colors look balanced")
                    
            except Exception as e:
                logger.exception("[Camera] Error during auto-correction")
        
        # Ejecutar en hilo separado para no bloquear la inicialización
        correction_thread = threading.Thread(target=delayed_correction, daemon=True)
        correction_thread.start()
    
    def _build_controls(self) -> Dict[str, Any]:
        """Build controls dictionary based on available camera controls"""
        controls = {
            "FrameRate": FRAME_RATE,
            "NoiseReductionMode": NOISE_REDUCTION_MODE
        }
        
        # Image quality controls
        if "Brightness" in self.available_controls:
            controls["Brightness"] = BRIGHTNESS
        
        if "Contrast" in self.available_controls:
            controls["Contrast"] = CONTRAST
            
        if "Saturation" in self.available_controls:
            controls["Saturation"] = SATURATION
            
        if "Sharpness" in self.available_controls:
            controls["Sharpness"] = SHARPNESS
        
        # Exposure controls
        if "ExposureTime" in self.available_controls and EXPOSURE_TIME is not None:
            controls["ExposureTime"] = EXPOSURE_TIME
            
        if "AnalogueGain" in self.available_controls:
            controls["AnalogueGain"] = ANALOGUE_GAIN
            
        if "DigitalGain" in self.available_controls:
            controls["DigitalGain"] = DIGITAL_GAIN
        
        # White balance
        if "AwbMode" in self.available_controls:
            controls["AwbMode"] = AWB_MODE
        
        # Focus controls
        if "AfMode" in self.available_controls:
            controls["AfMode"] = AF_MODE
            
        if "LensPosition" in self.available_controls and LENS_POSITION is not None:
            controls["LensPosition"] = LENS_POSITION
            
        return controls
    
    def update_control(self, control_name: str, value: Any) -> bool:
        """Update a single camera control"""
        if not self.picam2:
            logger.warning("[Camera] Camera not initialized")
            return False
            
        if control_name not in self.available_controls:
            logger.warning(f"[Camera] Control '{control_name}' not available")
            return False
        
        try:
            # Update the control
            self.picam2.set_controls({control_name: value})
            self.current_controls[control_name] = value
            
            logger.info(f"[Camera] Updated {control_name} to {value}")
            return True
            
        except Exception as e:
            logger.exception(f"[Camera] Failed to update {control_name}")
            return False
    
    def update_multiple_controls(self, controls: Dict[str, Any]) -> bool:
        """Update multiple camera controls at once"""
        if not self.picam2:
            logger.warning("[Camera] Camera not initialized")
            return False
        
        # Filter out unavailable controls
        valid_controls = {
            k: v for k, v in controls.items() 
            if k in self.available_controls
        }
        
        if not valid_controls:
            logger.warning("[Camera] No valid controls to update")
            return False
        
        try:
            self.picam2.set_controls(valid_controls)
            self.current_controls.update(valid_controls)
            
            logger.info(f"[Camera] Updated controls: {valid_controls}")
            return True
            
        except Exception as e:
            logger.exception("[Camera] Failed to update controls")
            return False
    
    def get_control_value(self, control_name: str) -> Optional[Any]:
        """Get current value of a control"""
        return self.current_controls.get(control_name)
    
    def get_available_controls(self) -> Dict[str, Any]:
        """Get all available camera controls and their limits"""
        return self.available_controls.copy()
    
    def get_current_controls(self) -> Dict[str, Any]:
        """Get current control values"""
        return self.current_controls.copy()
    
    def reset_to_defaults(self) -> bool:
        """Reset all controls to default values"""
        if not self.picam2:
            return False
        
        try:
            # Reset to default resolution and controls
            self.picam2.stop()
            # Handle rpicam-hello compatible resolution reset
            if CAMERA_WIDTH == 0 and CAMERA_HEIGHT == 0:
                self.current_resolution = None  # Use sensor default
            else:
                self.current_resolution = (CAMERA_WIDTH, CAMERA_HEIGHT)
            self.current_controls = self._build_controls()
            self.is_still_mode = False
            
            # Recreate configurations with defaults
            self.video_config = self.picam2.create_video_configuration(
                main={"size": self.current_resolution},
                controls=self.current_controls
            )
            
            self.still_config = self.picam2.create_still_configuration(
                main={"size": self.current_resolution},
                controls=self.current_controls
            )
            
            self.picam2.configure(self.video_config)
            self.picam2.start()
            
            logger.info("[Camera] Reset to default controls and resolution")
            return True
            
        except Exception as e:
            logger.exception("[Camera] Failed to reset controls")
            return False
    
    def set_manual_focus(self, lens_position: float) -> bool:
        """Set manual focus position (0.0 = infinity, higher = closer)"""
        if "LensPosition" not in self.available_controls:
            logger.warning("[Camera] Manual focus not supported")
            return False
        
        # First set to manual mode
        if not self.update_control("AfMode", 0):  # 0 = manual
            return False
            
        # Then set lens position
        return self.update_control("LensPosition", lens_position)
    
    def set_auto_focus(self, mode: int = 2) -> bool:
        """Set autofocus mode (1=auto, 2=continuous)"""
        if "AfMode" not in self.available_controls:
            logger.warning("[Camera] Autofocus not supported")
            return False
        
        return self.update_control("AfMode", mode)
    
    def set_resolution(self, width: int, height: int, update_stream: bool = True) -> bool:
        """
        Set camera resolution for video/stream mode
        
        Args:
            width: Width in pixels
            height: Height in pixels  
            update_stream: Whether to immediately update the running stream
            
        Returns:
            bool: True if successful
        """
        if not self.picam2:
            logger.warning("[Camera] Camera not initialized")
            return False
            
        try:
            new_resolution = (width, height)
            self.current_resolution = new_resolution
            
            if update_stream:
                # Stop current stream
                self.picam2.stop()
                
                # Create new configurations with current controls
                self.video_config = self.picam2.create_video_configuration(
                    main={"size": new_resolution},
                    controls=self.current_controls
                )
                
                self.still_config = self.picam2.create_still_configuration(
                    main={"size": new_resolution}, 
                    controls=self.current_controls
                )
                
                # Configure and restart
                config_to_use = self.still_config if self.is_still_mode else self.video_config
                self.picam2.configure(config_to_use)
                self.picam2.start()
                
                logger.info(f"[Camera] Resolution changed to {width}x{height}")
            else:
                # Just update configs for next mode switch
                self.video_config = self.picam2.create_video_configuration(
                    main={"size": new_resolution},
                    controls=self.current_controls
                )
                
                self.still_config = self.picam2.create_still_configuration(
                    main={"size": new_resolution},
                    controls=self.current_controls  
                )
                
                logger.info(f"[Camera] Resolution configs updated to {width}x{height}")
            
            return True
            
        except Exception as e:
            logger.exception(f"[Camera] Failed to set resolution to {width}x{height}")
            return False
    
    def get_current_resolution(self) -> tuple:
        """Get current camera resolution"""
        if self.current_resolution is None and self.picam2:
            # When using sensor defaults, get actual resolution from camera
            try:
                # Get the actual configured resolution
                config = self.picam2.camera_configuration()
                if config and 'main' in config and 'size' in config['main']:
                    actual_resolution = config['main']['size']
                    logger.info(f"[Camera] Actual sensor default resolution: {actual_resolution}")
                    return actual_resolution
                else:
                    # Fallback to typical IMX219 default
                    logger.info("[Camera] Using IMX219 typical default: 1640x1232")
                    return (1640, 1232)
            except Exception as e:
                logger.warning(f"[Camera] Could not get actual resolution: {e}")
                return (1640, 1232)  # IMX219 typical default
        return self.current_resolution or (640, 480)  # Fallback
    
    def switch_to_still_mode(self) -> bool:
        """Switch camera to still capture mode"""
        if not self.picam2 or self.is_still_mode:
            return False
            
        try:
            self.picam2.stop()
            self.picam2.configure(self.still_config)
            self.picam2.start()
            self.is_still_mode = True
            
            logger.info("[Camera] Switched to still capture mode")
            return True
            
        except Exception as e:
            logger.exception("[Camera] Failed to switch to still mode")
            return False
    
    def switch_to_video_mode(self) -> bool:
        """Switch camera to video/stream mode"""
        if not self.picam2 or not self.is_still_mode:
            return False
            
        try:
            self.picam2.stop()
            self.picam2.configure(self.video_config)
            self.picam2.start()
            self.is_still_mode = False
            
            logger.info("[Camera] Switched to video/stream mode")
            return True
            
        except Exception as e:
            logger.exception("[Camera] Failed to switch to video mode")
            return False
    
    def capture_image(self, file_path: str = None, resolution: tuple = None) -> Optional[str]:
        """
        Capture a still image
        
        Args:
            file_path: Optional file path to save image
            resolution: Optional resolution tuple (width, height) for this capture
            
        Returns:
            File path if saved, or numpy array if no file path provided
        """
        if not self.picam2:
            logger.warning("[Camera] Camera not initialized")
            return None
        
        try:
            # Switch to still mode if needed
            was_video_mode = not self.is_still_mode
            original_resolution = None
            
            # Set temporary resolution if specified
            if resolution and resolution != self.current_resolution:
                original_resolution = self.current_resolution
                self.set_resolution(resolution[0], resolution[1], False)
            
            # Switch to still mode for better quality
            if was_video_mode:
                self.switch_to_still_mode()
                time.sleep(0.1)  # Brief pause for stabilization
            
            # Capture image
            if file_path:
                self.picam2.capture_file(file_path)
                logger.info(f"[Camera] Image captured: {file_path}")
                result = file_path
            else:
                array = self.picam2.capture_array()
                logger.info("[Camera] Image captured as array")
                result = array
            
            # Restore original state
            if original_resolution:
                self.set_resolution(original_resolution[0], original_resolution[1], False)
                
            if was_video_mode:
                self.switch_to_video_mode()
                
            return result
                
        except Exception as e:
            logger.exception("[Camera] Failed to capture image")
            # Try to restore video mode on error
            if was_video_mode:
                try:
                    self.switch_to_video_mode()
                except:
                    pass
            return None
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Get comprehensive camera information"""
        if not self.picam2:
            return {"error": "Camera not initialized"}
        
        return {
            "resolution": self.current_resolution,
            "is_still_mode": self.is_still_mode,
            "available_controls": self.available_controls,
            "current_controls": self.current_controls,
            "roi": self.current_roi,
            "camera_properties": {
                "model": getattr(self.picam2, 'camera_model', 'Unknown'),
                "sensor_resolution": getattr(self.picam2, 'sensor_resolution', 'Unknown')
            }
        }

    # ======= SERVER-SIDE ZOOM AND PAN (ROI) METHODS =======
    
    def set_roi(self, x: float, y: float, width: float, height: float) -> bool:
        """
        Set Region of Interest (server-side zoom/pan)
        
        Args:
            x: X offset as fraction (0.0 to 1.0)
            y: Y offset as fraction (0.0 to 1.0) 
            width: Width as fraction (0.0 to 1.0)
            height: Height as fraction (0.0 to 1.0)
            
        Returns:
            bool: Success status
        """
        if not self.picam2:
            return False
            
        try:
            # Validate ROI bounds
            x = max(0.0, min(1.0, x))
            y = max(0.0, min(1.0, y))
            width = max(0.1, min(1.0 - x, width))  # Min 10% width
            height = max(0.1, min(1.0 - y, height))  # Min 10% height
            
            # Update ROI
            roi = (x, y, width, height)
            self.current_roi = roi
            
            # Apply ROI to camera using ScalerCrop control
            # ScalerCrop expects (x, y, width, height) in sensor coordinates
            sensor_info = self.picam2.camera_properties.get('ScalerCropMaximum', (0, 0, 1000, 1000))
            sensor_width = sensor_info[2]
            sensor_height = sensor_info[3]
            
            crop_x = int(x * sensor_width)
            crop_y = int(y * sensor_height)
            crop_w = int(width * sensor_width)
            crop_h = int(height * sensor_height)
            
            # Apply the crop
            controls = {"ScalerCrop": (crop_x, crop_y, crop_w, crop_h)}
            self.picam2.set_controls(controls)
            
            logger.info(f"[Camera] ROI set to {roi} (sensor coords: {crop_x}, {crop_y}, {crop_w}, {crop_h})")
            return True
            
        except Exception as e:
            logger.exception("[Camera] Failed to set ROI")
            return False
    
    def get_roi(self) -> tuple:
        """Get current Region of Interest"""
        return self.current_roi
    
    def reset_roi(self) -> bool:
        """Reset ROI to full frame"""
        return self.set_roi(0.0, 0.0, 1.0, 1.0)
    
    def zoom_roi(self, zoom_factor: float, center_x: float = 0.5, center_y: float = 0.5) -> bool:
        """
        Apply zoom to current ROI
        
        Args:
            zoom_factor: Zoom factor (> 1.0 = zoom in, < 1.0 = zoom out)
            center_x: Zoom center X as fraction (0.0 to 1.0)
            center_y: Zoom center Y as fraction (0.0 to 1.0)
            
        Returns:
            bool: Success status
        """
        if zoom_factor <= 0:
            return False
            
        x, y, width, height = self.current_roi
        
        # Calculate new dimensions
        new_width = width / zoom_factor
        new_height = height / zoom_factor
        
        # Calculate new position to maintain center point
        new_x = x + (center_x * width) - (center_x * new_width)
        new_y = y + (center_y * height) - (center_y * new_height)
        
        return self.set_roi(new_x, new_y, new_width, new_height)
    
    def pan_roi(self, delta_x: float, delta_y: float) -> bool:
        """
        Pan (move) current ROI
        
        Args:
            delta_x: X movement as fraction of current ROI width
            delta_y: Y movement as fraction of current ROI height
            
        Returns:
            bool: Success status
        """
        x, y, width, height = self.current_roi
        
        # Calculate movement in absolute coordinates
        move_x = delta_x * width
        move_y = delta_y * height
        
        new_x = x + move_x
        new_y = y + move_y
        
        return self.set_roi(new_x, new_y, width, height)

# Global camera controller instance
camera_controller = CameraController()