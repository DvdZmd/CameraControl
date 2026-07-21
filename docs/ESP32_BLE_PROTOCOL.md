# ESP32 y protocolo BLE

## Propósito

El ESP32 controla el cabezal pan/tilt y puede centralizar sensores ambientales.

La Raspberry Pi se comunica mediante BLE.

Nombre habitual del dispositivo:

`ESP32-CameraHead`

El firmware vigente es la fuente de verdad para:

- Nombre BLE.
- UUIDs.
- Pines.
- Comandos.
- Formato de telemetría.
- Persistencia.
- Rangos de servos.

## Comandos conocidos

Comandos históricos o actuales:

- `PAN_LEFT`
- `PAN_RIGHT`
- `TILT_UP`
- `TILT_DOWN`
- `CENTER`
- `STOP`
- `SET_SPEED:<valor>`
- `SET_ABS:<pan>:<tilt>`

No asumir el formato exacto de `SET_ABS` sin revisar el firmware.

## Flujo BLE

```text
Raspberry Pi
    |
    | scan
    v
ESP32 encontrado
    |
    | connect
    v
GATT service
    |
    +--> RX characteristic: comandos
    +--> TX characteristic: notificaciones
```

## Diagnóstico por capas

### 1. Adaptador

Comprobar:

```bash
rfkill list
bluetoothctl show
systemctl status bluetooth
```

### 2. Escaneo

Comprobar que el dispositivo aparece:

```bash
bluetoothctl scan on
```

### 3. Conexión

Problemas frecuentes:

- Dispositivo fuera de alcance.
- ESP32 reiniciado.
- Conexión anterior sin cerrar.
- BlueZ ocupado.
- Alimentación inestable.

### 4. Servicios

Confirmar UUIDs.

No reutilizar UUIDs recordados sin revisar firmware.

### 5. Notificaciones

Verificar:

- Suscripción exitosa.
- Callback.
- Decodificación.
- Separación de mensajes.
- Estado cacheado.

### 6. Escritura

Validar comando antes de escribir.

No enviar comandos a frecuencia excesiva.

### 7. Telemetría

Puede incluir:

- Pan actual.
- Tilt actual.
- Velocidad.
- Temperatura.
- Humedad.
- Soil.
- Estado.

Documentar el formato real cuando se confirme.

### 8. Reconexión

El controlador debe:

- Detectar desconexión.
- Limpiar cliente anterior.
- Evitar instancias duplicadas.
- Poder reconectar.
- Cerrar al terminar Flask.

## Sync y async

Bleak es asíncrono.

Si el backend ofrece wrappers síncronos:

- Revisar event loop.
- Evitar `asyncio.run()` repetido dentro de un loop activo.
- Evitar bloquear el thread de Flask indefinidamente.
- Aplicar timeouts.
- Propagar errores claros.

## Movimiento

Experiencia esperada:

- Click: movimiento de un paso.
- Mantener: movimiento continuo.
- Soltar: `STOP`.
- Centro: ambos ejes.
- Velocidad: seleccionable.
- Estado: visible.

El frontend debe contemplar:

- Pointer down.
- Pointer up.
- Pointer leave.
- Pointer cancel.
- Touch end.
- Pérdida de foco.
- `STOP` defensivo.

Es preferible que el ESP32 mantenga el movimiento tras un comando de inicio y se detenga con `STOP`, en lugar de recibir cientos de comandos por segundo.

## Servos

Hardware conocido:

- Dos SG90.
- Pan y tilt.
- Fuente dedicada.
- GND común con lógica.

No fijar pines ni pulsos sin revisar firmware.

Valores históricos:

- Pulso mínimo aproximado: 500 µs.
- Pulso máximo aproximado: 2400 µs.
- Centro aproximado: 1450 µs.

Estos valores pueden cambiar.

## Persistencia

Datos candidatos:

- Pan.
- Tilt.
- Velocidad.

Preferir `Preferences`/NVS.

Evitar escrituras por cada paso.

Estrategias:

- Debounce.
- Guardar al recibir `STOP`.
- Guardar tras inactividad.
- Guardar sólo si cambió.
- Validar al iniciar.

No mover inmediatamente a una posición inválida.

## Sensores

Sensores conocidos:

- DHT22.
- DS18B20.
- Soil capacitivo v1.2.

Pines históricos:

- Pan GPIO 22.
- Tilt GPIO 23.
- DHT22 GPIO 32.
- Soil GPIO 34.
- DS18B20 GPIO 12 o 13.

Verificar siempre el `.ino`.

## Errores eléctricos

Síntomas:

- BLE se desconecta al mover servo.
- ESP32 se reinicia.
- Valores de sensor erráticos.
- Movimiento tembloroso.
- Cámara o Raspberry Pi pierde conectividad.

Causas:

- Fuente insuficiente.
- Ground deficiente.
- Ruido.
- Cables largos.
- Regulador inestable.
- Pico de corriente.

Nunca alimentar servos desde 3.3 V.

## Cambios de protocolo

Antes de cambiar un comando:

1. Actualizar firmware.
2. Actualizar Python.
3. Actualizar frontend.
4. Actualizar pruebas.
5. Actualizar este documento.
6. Mantener compatibilidad o versionar protocolo.
