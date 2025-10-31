# examples/camera_control_examples.py
"""
Ejemplos de uso de los controles avanzados de cámara
Muestra cómo usar las nuevas funcionalidades programáticamente
"""

import sys
import os
import time

# Add parent directory to path to import camera modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camera.picam import camera_controller
from camera.camera_utils import (
    CameraPresets, apply_preset, validate_control_value,
    get_focus_distance_estimate, calculate_optimal_exposure,
    generate_focus_steps
)


def example_basic_controls():
    """Ejemplo básico de configuración de controles de imagen"""
    print("=== Ejemplo: Controles Básicos de Imagen ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Configurar brillo, contraste, saturación
    controls = {
        "Brightness": 0.2,    # Ligeramente más brillante
        "Contrast": 1.3,      # Más contraste
        "Saturation": 1.1,    # Colores más vivos
        "Sharpness": 1.2      # Más nitidez
    }
    
    print(f"Aplicando controles: {controls}")
    success = camera_controller.update_multiple_controls(controls)
    
    if success:
        print("✅ Controles aplicados correctamente")
        print(f"Valores actuales: {camera_controller.get_current_controls()}")
    else:
        print("❌ Error aplicando controles")


def example_focus_control():
    """Ejemplo de control de enfoque manual y automático"""
    print("\n=== Ejemplo: Control de Enfoque ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Configurar enfoque automático continuo
    print("1. Configurando enfoque automático continuo...")
    camera_controller.set_auto_focus(mode=2)  # Continuo
    time.sleep(2)
    
    # Cambiar a enfoque manual
    print("2. Cambiando a enfoque manual...")
    
    # Probar diferentes posiciones de enfoque
    focus_positions = [0.0, 8.0, 16.0, 24.0, 32.0]
    
    for pos in focus_positions:
        print(f"   Configurando enfoque en posición: {pos}")
        success = camera_controller.set_manual_focus(pos)
        if success:
            distance = get_focus_distance_estimate(pos)
            print(f"   ✅ Enfoque configurado - Distancia estimada: {distance}")
        else:
            print(f"   ❌ Error configurando enfoque en {pos}")
        time.sleep(1)
    
    # Volver a enfoque automático
    print("3. Volviendo a enfoque automático...")
    camera_controller.set_auto_focus(mode=2)


def example_exposure_control():
    """Ejemplo de control de exposición"""
    print("\n=== Ejemplo: Control de Exposición ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Exposición automática
    print("1. Configurando exposición automática...")
    camera_controller.update_control("ExposureTime", None)
    time.sleep(2)
    
    # Exposición manual para diferentes escenas
    scenes = ["daylight", "indoor", "low_light", "night"]
    
    for scene in scenes:
        exposure_time = calculate_optimal_exposure(scene)
        print(f"2. Configurando exposición para escena '{scene}': {exposure_time}µs")
        
        if exposure_time:
            success = camera_controller.update_control("ExposureTime", exposure_time)
            if success:
                print(f"   ✅ Exposición configurada: {exposure_time/1000}ms")
            else:
                print(f"   ❌ Error configurando exposición")
        time.sleep(1)
    
    # Volver a automático
    print("3. Volviendo a exposición automática...")
    camera_controller.update_control("ExposureTime", None)


def example_presets():
    """Ejemplo de uso de presets predefinidos"""
    print("\n=== Ejemplo: Presets Predefinidos ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    presets_to_test = ["daylight", "indoor", "low_light", "high_contrast"]
    
    for preset_name in presets_to_test:
        print(f"Aplicando preset: {preset_name}")
        success = apply_preset(camera_controller, preset_name)
        
        if success:
            print(f"✅ Preset '{preset_name}' aplicado")
            current_controls = camera_controller.get_current_controls()
            print(f"   Controles actuales: {current_controls}")
        else:
            print(f"❌ Error aplicando preset '{preset_name}'")
        
        time.sleep(2)


def example_focus_sweep():
    """Ejemplo de barrido de enfoque para encontrar el punto óptimo"""
    print("\n=== Ejemplo: Barrido de Enfoque ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Generar posiciones de enfoque
    focus_positions = generate_focus_steps(start=0.0, end=32.0, steps=8)
    print(f"Posiciones de enfoque a probar: {focus_positions}")
    
    # Configurar modo manual
    camera_controller.set_auto_focus(mode=0)  # Manual
    
    print("Iniciando barrido de enfoque...")
    for i, position in enumerate(focus_positions):
        print(f"Posición {i+1}/{len(focus_positions)}: {position:.1f}")
        
        # Configurar posición de enfoque
        success = camera_controller.update_control("LensPosition", position)
        if success:
            distance = get_focus_distance_estimate(position)
            print(f"   ✅ Enfoque en {position:.1f} - {distance}")
            
            # Aquí podrías capturar una imagen y analizar la nitidez
            # image_path = f"focus_test_{i:02d}_{position:.1f}.jpg"
            # camera_controller.capture_image(image_path)
            
        else:
            print(f"   ❌ Error en posición {position:.1f}")
        
        time.sleep(0.5)
    
    print("Barrido completado. Volviendo a enfoque automático...")
    camera_controller.set_auto_focus(mode=2)


def example_custom_configuration():
    """Ejemplo de configuración personalizada completa"""
    print("\n=== Ejemplo: Configuración Personalizada ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Configuración personalizada para fotografía macro
    macro_config = {
        "Brightness": 0.1,
        "Contrast": 1.4,
        "Saturation": 1.2,
        "Sharpness": 1.6,
        "AnalogueGain": 1.5,
        "AfMode": 0,          # Manual focus
        "LensPosition": 28.0, # Enfoque muy cercano
        "ExposureTime": 25000 # 25ms exposure
    }
    
    print("Configuración para fotografía macro:")
    for control, value in macro_config.items():
        print(f"  {control}: {value}")
    
    # Validar todos los controles antes de aplicar
    validated_config = {}
    for control, value in macro_config.items():
        is_valid, adjusted_value = validate_control_value(control, value)
        if is_valid:
            validated_config[control] = adjusted_value
        else:
            print(f"⚠️  Valor inválido para {control}: {value}")
    
    # Aplicar configuración validada
    success = camera_controller.update_multiple_controls(validated_config)
    
    if success:
        print("✅ Configuración macro aplicada correctamente")
        distance = get_focus_distance_estimate(macro_config["LensPosition"])
        print(f"   Distancia de enfoque: {distance}")
        print(f"   Tiempo de exposición: {macro_config['ExposureTime']/1000}ms")
    else:
        print("❌ Error aplicando configuración macro")


def example_resolution_control():
    """Ejemplo de control de resolución y modos"""
    print("\n=== Ejemplo: Control de Resolución ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Obtener información actual
    current_res = camera_controller.get_current_resolution()
    print(f"Resolución actual: {current_res[0]}x{current_res[1]}")
    print(f"Modo actual: {'Still' if camera_controller.is_still_mode else 'Video'}")
    
    # Probar diferentes resoluciones
    test_resolutions = [(640, 480), (1280, 720), (1920, 1080)]
    
    for width, height in test_resolutions:
        print(f"\n1. Configurando resolución a {width}x{height}...")
        success = camera_controller.set_resolution(width, height)
        
        if success:
            print(f"✅ Resolución configurada: {width}x{height}")
            
            # Probar cambio de modo
            print("2. Cambiando a modo still...")
            camera_controller.switch_to_still_mode()
            
            print("3. Capturando imagen de prueba...")
            image_path = f"test_resolution_{width}x{height}.jpg"
            result = camera_controller.capture_image(image_path)
            
            if result:
                print(f"✅ Imagen capturada: {image_path}")
            else:
                print("❌ Error capturando imagen")
            
            # Volver a modo video
            print("4. Volviendo a modo video...")
            camera_controller.switch_to_video_mode()
            
        else:
            print(f"❌ Error configurando resolución {width}x{height}")
        
        time.sleep(1)
    
    # Restaurar resolución original
    print(f"\n5. Restaurando resolución original: {current_res[0]}x{current_res[1]}...")
    camera_controller.set_resolution(current_res[0], current_res[1])


def example_get_camera_info():
    """Ejemplo de obtención de información de la cámara"""
    print("\n=== Información de la Cámara ===")
    
    if not camera_controller.picam2:
        print("❌ Cámara no disponible")
        return
    
    # Usar el nuevo método get_camera_info
    info = camera_controller.get_camera_info()
    
    print("Información general:")
    print(f"  Resolución: {info['resolution'][0]}x{info['resolution'][1]}")
    print(f"  Modo: {'Still' if info['is_still_mode'] else 'Video'}")
    
    if 'camera_properties' in info:
        props = info['camera_properties']
        print(f"  Modelo: {props.get('model', 'Unknown')}")
        print(f"  Resolución del sensor: {props.get('sensor_resolution', 'Unknown')}")
    
    print("\nControles disponibles:")
    available_controls = info['available_controls']
    for control, control_info in available_controls.items():
        print(f"  {control}: {control_info}")
    
    print("\nControles actuales:")
    current_controls = info['current_controls']
    for control, value in current_controls.items():
        print(f"  {control}: {value}")


def main():
    """Ejecutar todos los ejemplos"""
    print("🎥 Ejemplos de Control Avanzado de Cámara Raspberry Pi")
    print("=" * 60)
    
    try:
        # Obtener información de la cámara
        example_get_camera_info()
        
        # Control de resolución
        example_resolution_control()
        
        # Ejemplos básicos
        example_basic_controls()
        
        # Control de enfoque
        example_focus_control()
        
        # Control de exposición
        example_exposure_control()
        
        # Presets
        example_presets()
        
        # Barrido de enfoque
        example_focus_sweep()
        
        # Configuración personalizada
        example_custom_configuration()
        
        print("\n✅ Todos los ejemplos completados")
        
        # Resetear a valores por defecto
        print("\n🔄 Reseteando controles a valores por defecto...")
        camera_controller.reset_to_defaults()
        print("✅ Controles reseteados")
        
    except Exception as e:
        print(f"\n❌ Error durante los ejemplos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()