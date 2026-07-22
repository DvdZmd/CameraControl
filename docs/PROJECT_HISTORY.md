# Historia y decisiones del proyecto

## Propósito

Este documento conserva contexto histórico para evitar reintroducir errores o mezclar arquitecturas antiguas con el código actual.

No debe usarse como fuente de verdad por encima del código vigente.

## Etapa inicial

El proyecto comenzó como una aplicación Flask simple con:

- Página HTML.
- Stream MJPEG.
- Captura.
- Timelapse.
- Controles básicos.
- Cámara Raspberry Pi.

## I²C con Arduino

Arquitectura histórica:

### Arduino de servos

Dirección:

`0x10`

Responsabilidades:

- Pan.
- Tilt.
- Posiciones.
- EEPROM.
- Respuesta de estado.

### Arduino de sensores

Dirección:

`0x20`

Responsabilidades:

- DHT22.
- DS18B20.
- Soil.
- Envío de paquete binario.

Hubo errores históricos relacionados con:

- Cantidad de bytes.
- `struct.unpack`.
- Locks.
- Importaciones.
- Paquetes Python.
- Reintentos.

Esta arquitectura fue reemplazada o está siendo reemplazada por ESP32 BLE.

No mezclar código I²C antiguo con el controlador BLE actual salvo una migración explícita.

## ESP32 unificado

Objetivo:

- Unificar servos y sensores.
- Eliminar dos Arduino.
- Usar BLE.
- Simplificar cableado.
- Exponer telemetría.
- Persistir posición y velocidad.

Comandos conocidos:

- PAN_LEFT.
- PAN_RIGHT.
- TILT_UP.
- TILT_DOWN.
- CENTER.
- STOP.
- SET_SPEED.
- SET_ABS.

## Frontend

### HTML Flask

La interfaz actual puede ser HTML, CSS y JavaScript renderizados por Flask.

### Vue y Vite

Hubo experimentos con:

- Vue 3.
- Vite.
- Proxy `/api`.
- Puerto 5173.
- Hostnames `.local`.

Problema histórico:

```text
Blocked request. This host ("pi40.local") is not allowed.
```

Solución:

Configurar `server.allowedHosts` en Vite.

No asumir que Vue sigue siendo el frontend actual.

## Red y mDNS

Un problema de acceso por hostname fue causado por una VPN en Windows.

La IP funcionaba, pero `.local` no.

Antes de depurar Flask o mDNS, comprobar VPN y rutas de red.

## Streaming

Se intentó una refactorización hacia un thread productor con timestamps.

Resultado histórico:

- Congelamientos.
- Menor estabilidad.
- Rollback.

La obtención bajo demanda volvió a funcionar correctamente.

Esta decisión debe preservarse salvo evidencia nueva.

## Rotación y resolución

Se observaron diferencias por cámara:

- Camera v1 y v2 no se comportaban igual.
- Algunas resoluciones producían zoom aparente.
- La rotación dependía del modelo y pipeline.

No generalizar resultados entre sensores.

## Timelapse

El timelapse históricamente:

- Guarda imágenes por fecha.
- Usa thread.
- Usa `Event` para detenerse.
- Permite intervalo y resolución.

Revisar implementación actual antes de cambiar rutas o unidades.

## Persistencia

Los Arduino históricos usaban EEPROM.

En ESP32 moderno, considerar NVS mediante `Preferences`.

Persistir:

- Pan.
- Tilt.
- Velocidad.

Evitar escribir en flash continuamente.

## Tuya

La integración Tuya se agregó como hardware opcional.

Debe fallar de manera controlada.

No bloquear Flask durante el inicio por una API externa.

El dashboard no descubre ni da de alta dispositivos en la nube de Tuya. Sólo
permite registrar localmente dispositivos ya existentes en Tuya IoT Platform
mediante alias informativo editable, `device_id` y código de switch. Cuando la
API de Tuya permite leer detalle del dispositivo, el nombre remoto se muestra
como referencia separada del alias local.

## README

El README puede describir una etapa simplificada del proyecto y no incluir ESP32, BLE o Tuya.

Actualizarlo cuando la arquitectura se estabilice.

## Principio de mantenimiento

Cuando una versión fue confirmada como funcional sobre hardware real:

- Tratarla como baseline.
- No reemplazarla por elegancia teórica.
- Explicar riesgos.
- Probar regresiones.
- Mantener rollback sencillo.
