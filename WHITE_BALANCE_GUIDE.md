# 🎨 Guía de Balance de Blancos - Corrección del Tinte Azul

## 🚨 **Problema Identificado**

Las cámaras Raspberry Pi suelen mostrar un **tinte azul** marcado cuando se usan las configuraciones por defecto, especialmente comparado con las herramientas oficiales como `rpicam-hello`.

## 🔍 **Causa del Problema**

El problema estaba en la configuración inicial:
```python
# ANTES (Problemático)
AWB_MODE = 1  # Incandescent - Para luz cálida artificial
```

Esta configuración asume luz incandescente cálida y compensa demasiado hacia el azul cuando hay luz natural o LED.

## ✅ **Solución Implementada**

### **1. Configuración Corregida por Defecto**
```python
# AHORA (Correcto)
AWB_MODE = 0  # Auto - Detecta automáticamente el tipo de luz
```

### **2. Detección Automática de Tinte Azul**
- **Análisis de Color**: Analiza la imagen capturada en tiempo real
- **Detección Inteligente**: Calcula el ratio del canal azul vs otros colores
- **Corrección Automática**: Aplica el modo AWB óptimo según detección

### **3. Presets Corregidos**
```python
DAYLIGHT = {"AwbMode": 5}    # Para exteriores - luz natural
INDOOR = {"AwbMode": 1}      # Para interiores - luz artificial cálida  
LED_LIGHTING = {"AwbMode": 4}  # Para LEDs blancos modernos
```

## 🎛️ **Modos de Balance de Blancos**

| Modo | Nombre | Mejor Para |
|------|--------|------------|
| 0 | Auto | Condiciones mixtas/variables |
| 1 | Incandescent | Bombillas incandescentes cálidas |
| 2 | Tungsten | Luces halógenas |
| 3 | Fluorescent | Tubos fluorescentes |
| 4 | Indoor | LEDs blancos modernos |
| 5 | Daylight | Exteriores, luz solar |
| 6 | Cloudy | Exteriores nublados |

## 🚀 **Funciones Automáticas**

### **Corrección Automática al Iniciar**
```python
# Se ejecuta automáticamente 2 segundos después del inicio
def _schedule_auto_correction(self):
    # Analiza la imagen actual
    # Detecta tinte azul si existe
    # Aplica corrección automática
```

### **Detección Inteligente de Entorno**
```python
def auto_white_balance_by_environment():
    # Detecta hora del día
    # 6-18h: Daylight (luz natural)
    # 18-22h: Incandescent (luz artificial)  
    # 22-6h: Auto (condiciones variables)
```

## 🌐 **Uso en la Interfaz Web**

### **Control Manual**
1. **Selector AWB**: Elige el modo manualmente según tu entorno
2. **Auto-Detectar**: Análisis automático y corrección inteligente  
3. **Preset Balanceado**: Configuración optimizada que evita problemas

### **Uso Programático**
```python
# Corrección automática
from camera.camera_utils import detect_and_fix_blue_tint
success = detect_and_fix_blue_tint(camera_controller)

# Preset balanceado  
from camera.camera_utils import create_balanced_preset
balanced = create_balanced_preset()
camera_controller.update_multiple_controls(balanced)

# AWB inteligente
from camera.camera_utils import auto_white_balance_by_environment
optimal_mode = auto_white_balance_by_environment()
camera_controller.update_control("AwbMode", optimal_mode)
```

## 📊 **API REST para Balance de Blancos**

### **Detección Automática**
```http
POST /camera_awb/auto_detect
# Respuesta:
{
    "message": "Blue tint detected and corrected",
    "awb_mode": 5,
    "blue_tint_detected": true
}
```

### **Configuración Manual**
```http
POST /camera_awb/5  # Daylight mode
# Respuesta:
{
    "message": "White balance set to Daylight", 
    "awb_mode": 5,
    "mode_name": "Daylight"
}
```

### **Preset Balanceado**
```http
POST /camera_preset/balanced
# Aplica configuración optimizada que evita problemas comunes
```

## 🔧 **Diagnóstico y Solución de Problemas**

### **Síntomas del Tinte Azul**
- ✅ **Detectado automáticamente**: Ratio azul > 40% del total
- 👁️ **Visual**: Imagen se ve fría, azulada, poco natural
- 📊 **Análisis**: Canal azul dominante en promedio RGB

### **Soluciones Escalonadas**

1. **Automática** (Recomendado):
   ```javascript
   // En la interfaz web
   autoDetectWhiteBalance()
   ```

2. **Preset Balanceado**:
   ```javascript
   // Configuración que evita problemas
   applyBalancedPreset() 
   ```

3. **Manual según Entorno**:
   - **Exteriores**: Modo 5 (Daylight)
   - **LEDs blancos**: Modo 4 (Indoor)  
   - **Luz cálida**: Modo 1 (Incandescent)
   - **Condiciones mixtas**: Modo 0 (Auto)

## 📈 **Comparación: Antes vs Después**

### **Antes (Tinte Azul)**
- AWB Mode 1 (Incandescent) por defecto
- Sin análisis de color
- Sin corrección automática
- Imagen fría y azulada

### **Después (Natural)**  
- AWB Mode 0 (Auto) por defecto
- Análisis RGB automático
- Detección y corrección de tinte azul
- Configuración inteligente según entorno
- Imagen natural y balanceada

## 🎯 **Resultado**

- ✅ **Colores Naturales**: Comparable a `rpicam-hello`
- ✅ **Detección Automática**: Sin intervención manual necesaria
- ✅ **Configuración Inteligente**: Se adapta al entorno automáticamente
- ✅ **Control Granular**: Opciones manuales cuando se necesiten

¡Ahora tu cámara debería mostrar colores naturales desde el primer momento! 📷✨