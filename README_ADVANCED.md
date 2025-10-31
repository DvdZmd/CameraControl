# 📷 Raspberry Pi Camera Control - Configuración Avanzada

Sistema completo de control avanzado para cámara Raspberry Pi con configuraciones extensas de imagen, enfoque, exposición y presets predefinidos.

## 🆕 Nuevas Funcionalidades

### 🎨 **Controles de Calidad de Imagen**
- **Brillo**: Ajuste de luminosidad (-1.0 a 1.0)
- **Contraste**: Control de contraste (0.0 a 32.0) 
- **Saturación**: Intensidad de colores (0.0 a 32.0)
- **Nitidez**: Definición de bordes (0.0 a 16.0)

### 🔍 **Control de Enfoque Avanzado**
- **Enfoque Manual**: Control preciso de posición (0.0=∞ a 32.0=macro)
- **Enfoque Automático**: Modos single y continuo
- **Barrido de Enfoque**: Encuentra automáticamente el punto óptimo
- **Estimación de Distancia**: Calcula distancia aproximada según posición del lente

### 💡 **Control de Exposición Completo**
- **Exposición Automática**: Ajuste dinámico según condiciones
- **Exposición Manual**: Control preciso en microsegundos (100µs a 200ms)
- **Exposición por Escena**: Presets optimizados (día, interior, poca luz, noche)
- **Control de Ganancia**: Ganancia analógica y digital independientes

### 🎨 **Presets Predefinidos**
- **☀️ Daylight**: Optimizado para exteriores con luz natural
- **🏠 Indoor**: Configuración para interiores con luz artificial
- **🌙 Low Light**: Mayor sensibilidad para condiciones de poca luz
- **📈 High Contrast**: Contraste y nitidez realzados
- **⏱️ Timelapse**: Configuraciones estables para timelapses

### 🖱️ **Control Interactivo Mejorado**
- **Sliders Responsivos**: Control visual con valores en tiempo real
- **Soporte de Rueda del Ratón**: Ajuste fino con scroll del ratón
- **Validación de Rangos**: Previene valores fuera de límites
- **Feedback Visual**: Estimaciones de distancia y configuración

## 📁 **Estructura Actualizada del Proyecto**

```
CameraControl/
├── camera/
│   ├── picam.py              # Controlador principal mejorado
│   ├── camera_utils.py       # Utilidades y presets avanzados
│   └── timelapse.py          # Funcionalidad timelapse
├── examples/
│   └── camera_control_examples.py  # Ejemplos de uso programático
├── routes/
│   └── camera_routes.py      # API REST expandida
├── templates/
│   └── index.html            # Interfaz web completa
├── config.py                 # Configuraciones extendidas
└── README_ADVANCED.md        # Esta documentación
```

## 🚀 **Uso Rápido**

### **Interfaz Web**
1. Ejecutar la aplicación: `python app.py`
2. Abrir navegador: `http://localhost:5000`
3. Usar controles visuales para ajustar cámara en tiempo real

### **API REST Endpoints**

```python
# Obtener controles disponibles
GET /camera_controls

# Configurar control individual  
POST /camera_control/<nombre_control>
{"value": 1.5}

# Configurar múltiples controles
POST /camera_controls  
{"controls": {"Brightness": 0.2, "Contrast": 1.3}}

# Aplicar preset
POST /camera_preset/<nombre_preset>

# Control de enfoque manual
POST /camera_focus/manual
{"lens_position": 16.0}

# Control de enfoque automático
POST /camera_focus/auto
{"mode": 2}

# Exposición manual
POST /camera_exposure/manual
{"exposure_time": 25000}

# Exposición por escena
POST /camera_exposure/scene
{"scene_type": "indoor"}

# Reset completo
POST /camera_reset
```

### **Uso Programático**

```python
from camera.picam import camera_controller
from camera.camera_utils import apply_preset

# Configuración básica de imagen
controls = {
    "Brightness": 0.1,
    "Contrast": 1.2, 
    "Saturation": 1.1,
    "Sharpness": 1.0
}
camera_controller.update_multiple_controls(controls)

# Aplicar preset predefinido
apply_preset(camera_controller, "daylight")

# Enfoque manual preciso
camera_controller.set_manual_focus(16.0)

# Exposición para escena específica
exposure_time = calculate_optimal_exposure("indoor")
camera_controller.update_control("ExposureTime", exposure_time)
```

## 📋 **Rangos de Controles**

| Control | Rango | Descripción |
|---------|-------|-------------|
| Brightness | -1.0 a 1.0 | Brillo de imagen |
| Contrast | 0.0 a 32.0 | Contraste |
| Saturation | 0.0 a 32.0 | Saturación de color |
| Sharpness | 0.0 a 16.0 | Nitidez |
| AnalogueGain | 1.0 a 16.0 | Ganancia del sensor |
| DigitalGain | 1.0 a 64.0 | Ganancia digital |
| LensPosition | 0.0 a 32.0 | Posición enfoque (0=∞, 32=macro) |
| ExposureTime | 100µs a 200ms | Tiempo de exposición |

## 🎛️ **Modos de Enfoque**

- **0 - Manual**: Control total del usuario
- **1 - Auto Single**: Enfoque automático único
- **2 - Continuous**: Enfoque automático continuo

## 📸 **Modos de Balance de Blancos**

- **0**: Auto
- **1**: Incandescent  
- **2**: Tungsten
- **3**: Fluorescent
- **4**: Indoor
- **5**: Daylight
- **6**: Cloudy

## 🔧 **Configuración Avanzada**

### **Personalizar Presets**

```python
from camera.camera_utils import create_custom_preset

# Crear preset personalizado
mi_preset = {
    "Brightness": 0.15,
    "Contrast": 1.4,
    "Saturation": 1.1,
    "AfMode": 2,
    "ExposureTime": 15000
}

preset_validado = create_custom_preset(mi_preset)
camera_controller.update_multiple_controls(preset_validado)
```

### **Barrido de Enfoque Automático**

```python
from camera.camera_utils import generate_focus_steps

# Generar posiciones de prueba
positions = generate_focus_steps(start=0.0, end=32.0, steps=20)

# Probar cada posición
for pos in positions:
    camera_controller.set_manual_focus(pos)
    # Capturar imagen y analizar nitidez
    image = camera_controller.capture_image()
    sharpness_score = analyze_sharpness(image)
    print(f"Posición {pos}: Nitidez {sharpness_score}")
```

## 🔍 **Ejemplos Prácticos**

### **Fotografía Macro**
```python
macro_settings = {
    "Contrast": 1.6,
    "Sharpness": 2.0, 
    "LensPosition": 28.0,  # Muy cerca
    "ExposureTime": 30000,  # 30ms
    "AnalogueGain": 2.0
}
camera_controller.update_multiple_controls(macro_settings)
```

### **Fotografía Nocturna**
```python
night_settings = {
    "Brightness": 0.3,
    "AnalogueGain": 8.0,
    "DigitalGain": 4.0,
    "ExposureTime": 100000,  # 100ms
    "NoiseReductionMode": 2
}
camera_controller.update_multiple_controls(night_settings)
```

### **Timelapse Estabilizado**
```python
# Aplicar preset timelapse
apply_preset(camera_controller, "timelapse")

# Configuraciones adicionales para estabilidad
stable_settings = {
    "AfMode": 0,  # Manual para evitar cambios
    "LensPosition": 8.0,  # Enfoque fijo
    "ExposureTime": None,  # Automático para cambios de luz
    "AwbMode": 0  # Balance automático
}
camera_controller.update_multiple_controls(stable_settings)
```

## 🛠️ **Reutilización en Otros Proyectos**

### **Importar Módulos**
```python
# En tu proyecto
import sys
sys.path.append('/ruta/a/CameraControl')

from camera.picam import camera_controller
from camera.camera_utils import apply_preset, validate_control_value
```

### **Crear Instancia Personalizada**
```python
from camera.picam import CameraController

# Crear controlador independiente
my_camera = CameraController()

# Configurar según necesidades
my_camera.update_control("Brightness", 0.2)
my_camera.set_manual_focus(12.0)
```

## 🚨 **Compatibilidad y Requerimientos**

- **Hardware**: Raspberry Pi con cámara oficial o compatible
- **Software**: Picamera2, Python 3.7+
- **Dependencias**: OpenCV, Flask (para web), NumPy

### **Instalación**
```bash
# Instalar dependencias
pip install picamera2 opencv-python flask numpy

# Verificar hardware
python examples/camera_control_examples.py
```

## 📈 **Rendimiento y Optimización**

- **Validación de Controles**: Previene errores antes de aplicar cambios
- **Control por Lotes**: Actualiza múltiples configuraciones en una sola operación
- **Cache de Estado**: Mantiene estado actual sin consultar hardware constantemente
- **Manejo de Errores**: Recuperación automática ante fallos de configuración

## 🔄 **Integración Continua**

El sistema está diseñado para ser:
- **Modular**: Cada componente es independiente
- **Reutilizable**: Fácil integración en otros proyectos
- **Extensible**: Nuevos controles se agregan fácilmente
- **Robusto**: Manejo completo de errores y validaciones

Este sistema proporciona control completo y profesional sobre la cámara Raspberry Pi, permitiendo desde ajustes básicos hasta configuraciones avanzadas para fotografía especializada.