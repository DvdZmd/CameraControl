# AGENTS.md

## Proyecto

CameraControl es una plataforma IoT para Raspberry Pi orientada al control de cámara, streaming MJPEG, captura de imágenes, timelapse, control pan/tilt mediante ESP32 por BLE, sensores e integración con dispositivos Tuya.

Repositorio principal:

`https://github.com/DvdZmd/CameraControl`

El código actual del repositorio es la fuente de verdad. La documentación histórica, el README o conversaciones anteriores pueden estar desactualizados.

## Idioma y nivel técnico

- Responde en español salvo que el usuario pida otro idioma.
- El propietario del proyecto tiene experiencia avanzada en backend, APIs, .NET, Python, Raspberry Pi, ESP32, electrónica e IoT.
- Sé directo, técnico y práctico.
- No expliques conceptos básicos salvo que sean necesarios para resolver el problema.

## Prioridades

1. No dañar el hardware.
2. Mantener estable el streaming.
3. Preservar funcionalidades confirmadas.
4. Evitar regresiones en frontend, API y protocolo BLE.
5. Manejar fallas de hardware de manera controlada.
6. Mantener la arquitectura modular.
7. Facilitar diagnóstico mediante logs.
8. Hacer cambios pequeños, claros y verificables.

## Fuente de verdad

Antes de modificar una función:

1. Inspecciona los archivos involucrados.
2. Revisa llamadas, imports, rutas y dependencias.
3. Busca contratos compartidos con frontend, ESP32 o Tuya.
4. Compara documentación y código.
5. Si existe contradicción, prioriza el código actual.
6. Señala explícitamente los supuestos no verificados.

No inventes archivos, clases, endpoints, comandos, pines o comportamientos.

## Arquitectura esperada

El proyecto utiliza una arquitectura modular similar a:

- `app.py`: punto de entrada.
- `app_factory.py`: creación y configuración de Flask.
- `config.py`: configuración.
- `routes/`: blueprints HTTP.
- `camera/` o dependencia `rpicam-z`: lógica de cámara.
- `esp32/`: comunicación BLE.
- `tuya/`: integración Tuya.
- `database/`: SQLAlchemy y SQLite.
- `logs/`: logging.
- `templates/`: HTML.
- `static/`: CSS y JavaScript.

No concentres lógica de hardware o negocio en `app.py` ni en las rutas.

Las rutas deben validar entrada, delegar operaciones y traducir errores a respuestas HTTP.

## Documentación por área

Antes de trabajar en una sección, consulta:

- Arquitectura general: `docs/ARCHITECTURE.md`
- Cámara, Picamera2, streaming y timelapse: `docs/CAMERA_PIPELINE.md`
- ESP32, BLE, comandos y persistencia: `docs/ESP32_BLE_PROTOCOL.md`
- Raspberry Pi, cámaras, sensores, servos y alimentación: `docs/HARDWARE.md`
- Decisiones históricas y código legado: `docs/PROJECT_HISTORY.md`
- Diagnóstico: `docs/TROUBLESHOOTING.md`

## Reglas para cambios

- Prefiere cambios incrementales.
- No hagas refactorizaciones masivas para resolver errores aislados.
- No elimines funcionalidad no relacionada.
- No cambies contratos de API sin revisar frontend y consumidores.
- No cambies el protocolo BLE de un solo lado.
- No cambies pines sin revisar el firmware vigente.
- No introduzcas concurrencia compleja sin necesidad.
- No afirmes que una prueba física fue realizada si no ocurrió.
- No guardes secretos en el repositorio.
- No alimentes servos desde 3.3 V de Raspberry Pi o ESP32.
- No escribas continuamente en la flash del ESP32.

## Manejo de hardware opcional

La aplicación debe poder iniciar aunque falte hardware secundario.

Comportamiento esperado:

- Cámara ausente: error claro, preferentemente HTTP 503.
- ESP32 ausente: cámara y servidor siguen funcionando.
- Tuya no disponible: warning y continuación.
- Autofocus no soportado: control oculto o deshabilitado.
- Sensor no disponible: estado explícito, no valores inventados.

## Cámara y streaming

La estabilidad del streaming MJPEG es crítica.

No reemplaces la obtención de frames bajo demanda por un productor permanente, colas o buffering sin una necesidad demostrada.

Antes de modificar el pipeline, revisa:

- Propiedad de la instancia Picamera2.
- Acceso concurrente.
- Locks.
- Captura estática y reconfiguración.
- Timelapse.
- Múltiples clientes.
- Desconexión del navegador.
- Recuperación ante excepciones.
- Crecimiento de memoria.

Preserva el boundary multipart y bytes JPEG válidos.

Verifica controles soportados antes de aplicarlos.

## ESP32 y BLE

Analiza BLE por etapas:

1. Adaptador Bluetooth.
2. Escaneo.
3. Conexión GATT.
4. Servicios y characteristics.
5. Suscripción a notificaciones.
6. Escritura de comandos.
7. Telemetría.
8. Reconexión y limpieza.

Evita múltiples controladores BLE para el mismo dispositivo.

Ten cuidado al mezclar APIs sync y async.

Para pan/tilt, la experiencia deseada suele ser:

- Click corto: un paso.
- Botón mantenido: movimiento continuo.
- Al soltar: `STOP`.
- Centro: ambos ejes.
- Velocidad seleccionable.
- Estado actual visible cuando exista telemetría.

Confirma siempre el protocolo vigente en Python y en el firmware.

## Persistencia ESP32

Para ESP32 moderno, prefiere `Preferences`/NVS salvo que el firmware vigente requiera EEPROM.

Persistir sólo cuando sea necesario:

- Al finalizar movimiento.
- Tras un debounce.
- Cuando el valor cambió realmente.
- Antes de reinicios controlados cuando sea posible.

Validar posiciones y velocidad al restaurar.

Evitar movimientos bruscos durante el arranque.

## Configuración y secretos

Usar variables de entorno o `.env` excluido por `.gitignore` para:

- Credenciales Tuya.
- Tokens.
- API keys.
- Secret key de Flask.
- Contraseñas.
- Datos de red.

Mantener `.env.example` sin secretos reales.

## Calidad del código

En Python:

- Nombres claros.
- Type hints cuando aporten valor.
- Unidades explícitas.
- Validación de rangos.
- Logging en lugar de `print` permanente.
- Excepciones específicas.
- `try/finally` en reconfiguraciones de hardware.
- Respuestas JSON consistentes.
- Códigos HTTP correctos.

## Pruebas

Distingue siempre:

### Sin hardware

- Validación de payloads.
- Traducción de comandos.
- Respuestas HTTP.
- Persistencia.
- Configuración.
- Mocks de cámara.
- Mocks de BLE.
- Mocks de Tuya.

### Con hardware

- Streaming real.
- Resolución.
- Captura.
- Autofocus.
- Exposición.
- Timelapse.
- Movimiento pan/tilt.
- Reconexión BLE.
- Telemetría.
- Sensores.
- Estabilidad eléctrica.

No presentes razonamiento o mocks como validación física.

## Entrega de cambios

Al modificar código:

1. Explica la causa.
2. Indica los archivos afectados.
3. Entrega el cambio completo o un diff inequívoco.
4. Mantén imports correctos.
5. Incluye pasos de prueba.
6. Señala riesgos de hardware.
7. Declara supuestos.
8. Actualiza documentación si cambia arquitectura, API o protocolo.

No hagas push directo a `main` salvo instrucción explícita.
