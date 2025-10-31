# 🖥️ Zoom y Pan del Lado del Servidor - Documentación

## 🎯 Concepto: ROI (Region of Interest)

El zoom y pan del lado del servidor utiliza la funcionalidad **ROI (Region of Interest)** de Picamera2. Esto significa que:

- 📷 **La cámara física** captura solo una región específica del sensor
- 🌐 **Todos los dispositivos** conectados ven exactamente la misma vista
- ⚡ **Mejor rendimiento** porque procesa menos píxeles
- 🎯 **Zoom real** a nivel de hardware, no solo amplificación digital

## 🔄 Diferencia: Cliente vs Servidor

### **Zoom del Cliente (Frontend)**
```javascript
// Solo afecta la vista local del navegador
imageZoom.scale = 2.0;  // 200% zoom local
image.style.transform = `scale(2.0)`;
```

### **Zoom del Servidor (ROI)**
```python
# Afecta la captura física de la cámara
camera_controller.set_roi(0.25, 0.25, 0.5, 0.5)  # Zoom 2x en el centro
# Todos los clientes ven esta vista
```

## ⚙️ Implementación Técnica

### **Sistema de Coordenadas ROI**
- **Coordenadas**: Fracciones de 0.0 a 1.0
- **Formato**: `(x, y, width, height)`
- **Ejemplo**: `(0.25, 0.25, 0.5, 0.5)` = zoom 2x en el centro

### **Configuración en config.py**
```python
# ROI por defecto (frame completo)
CAMERA_ROI = (0.0, 0.0, 1.0, 1.0)  # x, y, width, height

# Dataclass configuration
@dataclass
class CameraConfig:
    roi: tuple = (0.0, 0.0, 1.0, 1.0)  # Server-side zoom/pan
```

## 🛠️ API Endpoints Implementados

### **1. GET /camera_roi**
Obtiene el ROI actual del servidor
```json
{
  "roi": {"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5},
  "zoom_level": 2.0,
  "is_zoomed": true
}
```

### **2. POST /camera_roi**
Establece un ROI específico
```json
{
  "x": 0.25,
  "y": 0.25,
  "width": 0.5,
  "height": 0.5
}
```

### **3. POST /camera_zoom**
Aplica zoom manteniendo el centro
```json
{
  "zoom_factor": 1.2,  // 1.2x más zoom
  "center_x": 0.5,     // Centro X (0.0-1.0)
  "center_y": 0.5      // Centro Y (0.0-1.0)
}
```

### **4. POST /camera_pan**
Mueve el ROI actual
```json
{
  "delta_x": 0.1,  // Mover 10% hacia la derecha
  "delta_y": -0.1  // Mover 10% hacia arriba
}
```

### **5. POST /camera_roi/reset**
Resetea a frame completo
```json
{
  "message": "ROI reset to full frame",
  "zoom_level": 1.0
}
```

## 🎮 Controles de Interfaz

### **Zoom Controls**
```html
<button onclick="serverZoom(1.2)">🔍+ Zoom In</button>
<button onclick="serverZoom(0.8)">🔍- Zoom Out</button>  
<button onclick="resetServerZoom()">🔍↺ Reset</button>
```

### **Pan Controls (8 direcciones)**
```html
<!-- Direcciones cardinales -->
<button onclick="serverPan(-0.1, 0)">⬅️</button>  <!-- Izquierda -->
<button onclick="serverPan(0.1, 0)">➡️</button>   <!-- Derecha -->
<button onclick="serverPan(0, -0.1)">⬆️</button>  <!-- Arriba -->
<button onclick="serverPan(0, 0.1)">⬇️</button>   <!-- Abajo -->

<!-- Direcciones diagonales -->
<button onclick="serverPan(-0.1, -0.1)">↖️</button> <!-- Arriba-izq -->
<button onclick="serverPan(0.1, -0.1)">↗️</button>  <!-- Arriba-der -->
<button onclick="serverPan(-0.1, 0.1)">↙️</button>  <!-- Abajo-izq -->
<button onclick="serverPan(0.1, 0.1)">↘️</button>   <!-- Abajo-der -->
```

## 💡 Funciones JavaScript Implementadas

### **getServerROI()**
```javascript
async function getServerROI() {
    const result = await apiRequest('/camera_roi');
    // Actualiza UI con estado actual
}
```

### **serverZoom(factor)**
```javascript
async function serverZoom(zoomFactor) {
    const result = await apiRequest('/camera_zoom', 'POST', {
        zoom_factor: zoomFactor,
        center_x: 0.5,  // Centro actual
        center_y: 0.5
    });
}
```

### **serverPan(deltaX, deltaY)**
```javascript
async function serverPan(deltaX, deltaY) {
    const result = await apiRequest('/camera_pan', 'POST', {
        delta_x: deltaX,
        delta_y: deltaY
    });
}
```

## 📊 Información en Tiempo Real

### **Indicadores Visuales**
- **Zoom Level**: `1.0x` (sin zoom) a `10.0x+` (zoom máximo)
- **ROI Info**: `x:0.25, y:0.25, w:0.5, h:0.5` (coordenadas actuales)
- **Status Messages**: Feedback en tiempo real de operaciones

### **Auto-actualización**
```javascript
// Se carga automáticamente al iniciar la página
document.addEventListener('DOMContentLoaded', function() {
    getServerROI(); // Carga estado actual del servidor
});
```

## 🔧 Métodos del CameraController

### **set_roi(x, y, width, height)**
```python
def set_roi(self, x: float, y: float, width: float, height: float) -> bool:
    # Valida y aplica ROI usando ScalerCrop
    # Convierte coordenadas fraccionarias a coordenadas del sensor
    # Aplica límites mínimos (10% width/height)
```

### **zoom_roi(zoom_factor, center_x, center_y)**
```python
def zoom_roi(self, zoom_factor: float, center_x: float = 0.5, center_y: float = 0.5) -> bool:
    # Calcula nuevo ROI manteniendo el punto central
    # zoom_factor > 1.0 = zoom in
    # zoom_factor < 1.0 = zoom out
```

### **pan_roi(delta_x, delta_y)**
```python
def pan_roi(self, delta_x: float, delta_y: float) -> bool:
    # Mueve ROI por delta relativo al tamaño actual
    # delta_x/y: fracción del ancho/alto actual del ROI
```

## 🌟 Ventajas del Zoom/Pan del Servidor

### **1. Sincronización Global**
- ✅ Todos los dispositivos ven la **misma vista exacta**
- ✅ Cambios se aplican **instantáneamente** a todos los clientes
- ✅ **Un control maestro** para múltiples dispositivos

### **2. Mejor Rendimiento**
- ✅ **Menos píxeles** procesados en el pipeline de video
- ✅ **Menor ancho de banda** para streaming
- ✅ **Zoom óptico** real, no digital

### **3. Casos de Uso Prácticos**
- 🎯 **Vigilancia**: Enfocar área específica de interés
- 📹 **Streaming**: Control de cámara remoto profesional  
- 🔬 **Microscopia**: Zoom preciso para análisis detallado
- 📡 **Monitoreo**: Vista coordinada entre múltiples operadores

## 🔄 Flujo de Trabajo Típico

### **Escenario: Control Remoto de Cámara**
1. **Dispositivo A** (localhost) aplica zoom 3x en una esquina
2. **ROI** se actualiza en el servidor: `(0.0, 0.0, 0.33, 0.33)`
3. **Dispositivo B** (red local) se conecta y ve automáticamente la vista con zoom
4. **Dispositivo C** (móvil) también ve la misma vista enfocada
5. Cualquier dispositivo puede **cambiar el ROI** y afectar a todos los demás

### **Integración con Zoom del Cliente**
- **Zoom del servidor**: Define qué región del sensor capturar
- **Zoom del cliente**: Permite inspección detallada de la vista del servidor
- **Combinación**: Zoom del servidor 3x + zoom del cliente 2x = inspección 6x total

¡El sistema de zoom/pan del servidor está completamente implementado y listo para usar! 🎉