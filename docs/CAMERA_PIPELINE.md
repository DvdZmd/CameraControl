# Pipeline de cámara

## Tecnologías

El stack de cámara puede incluir:

- Raspberry Pi Camera.
- Picamera2.
- libcamera / rpicam.
- `rpicam-z`.
- OpenCV.
- MJPEG multipart.
- Captura JPEG.
- Timelapse.

El código actual determina qué biblioteca posee la instancia real de cámara.

## Cámaras conocidas

- Camera v1.3 — OV5647 — 5 MP.
- Camera v2.1 — IMX219 — 8 MP.
- Camera v3 — IMX708 — 12 MP y autofocus.
- Arducam IMX519 — utilizada en pruebas previas.

Las capacidades cambian por sensor.

No asumir:

- Autofocus universal.
- Misma resolución máxima.
- Mismo campo de visión.
- Mismos modos de sensor.
- Mismos controles.
- Mismo comportamiento al rotar.

## Streaming MJPEG

El stream suele ser una respuesta:

```text
multipart/x-mixed-replace; boundary=frame
```

Cada frame debe incluir:

```text
--frame
Content-Type: image/jpeg

<JPEG bytes>
```

El generador debe:

- Emitir bytes JPEG válidos.
- Incluir pausas razonables.
- Detenerse ante cierre o error.
- Evitar loops que consuman CPU sin límite.
- No acumular frames.
- No mantener referencias innecesarias.
- Manejar cámara no disponible.

## Streaming sincronizado

Puede añadir headers como:

- `X-Frame-Id`
- `X-Timestamp-Wall-Ns`
- `X-Timestamp-Mono-Ns`

Estos valores representan timestamps del software salvo que se confirme que provienen del sensor.

No confundir reloj de pared con reloj monotónico.

## Estabilidad

Una implementación histórica con productor permanente de frames provocó congelamientos.

La obtención bajo demanda fue más estable.

No introducir:

- Producer thread.
- Buffer global.
- Cola sin límite.
- Cache de frames.
- Multiplexor complejo.

salvo que exista un problema medido que lo justifique.

## Concurrencia

Antes de cambiar la cámara, revisar:

- Quién crea la instancia.
- Cuántas rutas la utilizan.
- Si existe lock.
- Si captura y stream comparten configuración.
- Si el timelapse reconfigura el sensor.
- Si hay múltiples clientes.
- Si el objeto Picamera2 es thread-safe.
- Si una excepción deja la cámara detenida.

Cuando una operación reconfigura temporalmente la cámara:

```python
previous_state = capture_current_state()
try:
    stop_stream()
    apply_still_configuration()
    capture()
finally:
    restore(previous_state)
```

El código exacto depende de la biblioteca vigente.

## Resolución

Cambiar resolución puede requerir:

1. Detener cámara.
2. Crear nueva configuración.
3. Configurar.
4. Iniciar.
5. Esperar estabilización.
6. Actualizar estado.

No asumir que una resolución arbitraria es válida.

Validar contra:

- Capacidades del sensor.
- Modos disponibles.
- Límites de memoria.
- Aspect ratio.
- Requisitos de alineación.

## Controles

### Controles del ISP

Ejemplos:

- Brightness.
- Contrast.
- Saturation.
- Sharpness.

Suelen aplicarse dinámicamente.

### Controles del sensor

Ejemplos:

- ExposureTime.
- AnalogueGain.
- AeEnable.
- AfMode.
- LensPosition.

Dependen de la cámara.

Antes de enviar un control:

- Verificar que existe.
- Validar tipo.
- Validar rango.
- Documentar unidad.
- Manejar error de hardware.

## Exposición

`ExposureTime` suele expresarse en microsegundos.

No mezclar:

- segundos,
- milisegundos,
- microsegundos.

Al usar exposición manual, puede ser necesario desactivar AE.

No asumir que todos los controles se aplican inmediatamente.

## Autofocus

Camera v3 puede soportar:

- Enfoque continuo.
- Enfoque automático.
- Enfoque manual.
- Posición de lente.

Las cámaras v1 y v2 normalmente no tienen autofocus.

El frontend debe reaccionar a capacidades detectadas.

## Captura estática

Para capturas personalizadas:

- Validar ancho y alto.
- Evitar reconfiguración concurrente.
- Restaurar stream.
- Usar `try/finally`.
- Devolver JPEG.
- Nombrar archivo claramente.
- No dejar la cámara en estado inconsistente.

## Timelapse

El timelapse debe manejar:

- Estado start/stop.
- Intervalo.
- Resolución.
- Directorio.
- Nombre de archivo.
- Cancelación.
- Excepciones.
- Reinicio de aplicación.

Usar `threading.Event` o mecanismo equivalente para detener de forma limpia.

No iniciar múltiples timelapses simultáneos.

## Errores

La cámara ausente debería generar una respuesta clara, por ejemplo HTTP 503.

No bloquear el arranque completo si la arquitectura soporta una cámara no disponible.

## Pruebas

### Sin hardware

- Validación de resoluciones.
- Validación de controles.
- Respuesta 503.
- Formato multipart.
- Traducción de errores.
- Estado de timelapse.

### Con hardware

- Stream prolongado.
- Dos clientes simultáneos.
- Captura mientras hay stream.
- Cambio de resolución.
- Timelapse.
- Desconexión del navegador.
- Reinicio de cámara.
- Autofocus.
- Baja luz.
- Uso de memoria.
