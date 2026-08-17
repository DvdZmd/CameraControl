# Instancias y almacenamiento

## Perfil e instancia

El perfil define funcionalidades; la instancia identifica una instalación
física y sus datos. Son dimensiones independientes:

```dotenv
CAMERACONTROL_PROFILE=starseek
CAMERACONTROL_INSTANCE=observatorio
```

Dos instalaciones pueden compartir perfil sin compartir SQLite, capturas o
logs.

## Compatibilidad con instalaciones existentes

Sin `CAMERACONTROL_INSTANCE`, o con su valor `default`, CameraControl conserva:

```text
database/app.db
timelapse/
logs/server.log
```

No se mueven, copian ni eliminan datos durante el arranque.

## Instancias nombradas

Una instancia distinta de `default` usa automáticamente:

```text
data/<instancia>/
├── app.db
├── timelapse/
└── logs/
    └── server.log
```

Ejemplo:

```dotenv
CAMERACONTROL_PROFILE=fungiforge_monitor
CAMERACONTROL_INSTANCE=cultivo_garage
```

El nombre debe comenzar con una letra minúscula o número y contener únicamente
minúsculas, números, guion o guion bajo. Se limita a 64 caracteres. Valores con
separadores de ruta o traversal impiden el arranque.

`data/` está excluido de Git.

## Directorio raíz y overrides

La raíz de todas las instancias puede cambiarse mediante:

```dotenv
CAMERACONTROL_DATA_DIR=/srv/cameracontrol
```

La instancia anterior utilizaría `/srv/cameracontrol/cultivo_garage/`.

También existen overrides individuales:

```dotenv
DATABASE_PATH=/mnt/ssd/cultivo.db
TIMELAPSE_DIR=/mnt/capturas/fungi
LOG_FILE_PATH=/var/log/cameracontrol/fungi.log
```

Las rutas relativas se resuelven contra la raíz del repositorio. Cada override
tiene precedencia sobre el path derivado de la instancia.

Si un `.env` existente define `TIMELAPSE_DIR=./timelapse` o
`LOG_FILE_PATH=./logs/server.log`, esos valores siguen siendo overrides. Deben
eliminarse o comentarse para que una instancia nombrada obtenga aislamiento
automático en esos recursos.

## Directorios y archivos

Al iniciar, CameraControl crea los directorios requeridos para SQLite,
timelapse y logs. No crea el archivo SQLite ni el log directamente; sus
respectivos servicios lo hacen cuando corresponde.

Cambiar de instancia crea o selecciona otro estado. No migra:

- configuración de cámara;
- configuración ESP32;
- dispositivos Tuya;
- historial de sensores;
- configuración o capturas de timelapse;
- logs almacenados en SQLite.

Una migración debe hacerse manualmente con el servicio detenido y una copia de
seguridad previa.

## Contrato HTTP

`GET /api/system/capabilities` incluye `instance`, pero nunca paths internos:

```json
{
  "api_version": "1",
  "profile": "starseek",
  "instance": "observatorio",
  "features": {}
}
```

El dashboard técnico muestra `perfil / instancia` para reducir errores de
operación.
