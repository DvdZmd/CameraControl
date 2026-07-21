# Política de Seguridad

Este documento describe las prácticas de seguridad para el proyecto CameraControl, incluyendo la gestión de secretos y el plan de respuesta ante incidentes.

## 1. Gestión de Secretos (Prevención)

La regla fundamental es **nunca cometer secretos en el repositorio de Git**.

### 1.1. ¿Qué se considera un secreto?

Cualquier información que, si se expone, podría comprometer la seguridad, privacidad o funcionamiento del sistema. Esto incluye, pero no se limita a:

- **`FLASK_SECRET_KEY`**: Clave para firmar sesiones de Flask.
- **Credenciales de Tuya**: `ACCESS_ID`, `ACCESS_KEY`, `DEVICE_ID`, `LOCAL_KEY`.
- **Otras API Keys o Tokens**: Para cualquier servicio de terceros.
- **Contraseñas**: Para bases de datos, servicios, etc.
- **Datos de red sensibles**: Nombres y contraseñas de Wi-Fi.

### 1.2. ¿Cómo gestionar los secretos?

1.  **Archivo `.env`**: Todos los secretos deben almacenarse en un archivo `.env` en la raíz del proyecto.
2.  **`.gitignore`**: El archivo `.env` **debe** estar listado en `.gitignore` para prevenir su subida accidental.
3.  **Archivo `.env.example`**: Se debe mantener un archivo `.env.example` en el repositorio. Este archivo sirve como plantilla, listando todas las variables de entorno necesarias pero con valores vacíos o genéricos. **Nunca debe contener secretos reales.**

#### Ejemplo de `.env.example`

```
FLASK_SECRET_KEY=""
TUYA_ACCESS_ID=""
TUYA_ACCESS_KEY=""
TUYA_DEVICE_ID=""
TUYA_LOCAL_KEY=""
```

### 1.3. Carga de secretos en la aplicación

La aplicación (ej. `config.py` o `app_factory.py`) debe cargar estas variables desde el entorno. La `FLASK_SECRET_KEY` es un caso crítico; `app_factory.py` debe cargarla desde una variable de entorno y no usar un valor quemado en el código.

## 2. Plan de Respuesta a Fuga de Credenciales

Si un secreto es accidentalmente comiteado y subido a un repositorio (público o privado), se debe asumir que ha sido comprometido. Sigue estos pasos de inmediato:

### Paso 1: Rotar las credenciales comprometidas

Esta es la acción más urgente. Invalida inmediatamente los secretos expuestos.

- **Credenciales de Tuya**: En la consola de Tuya IoT Cloud, genera un nuevo `AccessID/Secret`. Si una `local_key` de dispositivo fue expuesta, es posible que necesites re-vincular el dispositivo para obtener una nueva.
- **Flask Secret Key**: Genera una nueva clave. Esto invalidará todas las sesiones de usuario existentes.
- **Otras API Keys**: Revoca la clave expuesta y genera una nueva en el panel del proveedor de servicios.

### Paso 2: Eliminar el secreto de los archivos del repositorio

Reemplaza el secreto en el código con un método de carga desde el entorno (ej. `os.getenv('MY_SECRET')`) y comitea el cambio. Asegúrate de que el archivo `.env` esté en `.gitignore`.

### Paso 3: Purgar el secreto del historial de Git

Eliminar un secreto del último commit no es suficiente; permanece en el historial. Es necesario reescribir la historia del repositorio para eliminar todo rastro.

**Herramienta recomendada: `git-filter-repo`**

```bash
# 1. Instalar la herramienta si no la tienes
# pip install git-filter-repo

# 2. (Opcional pero recomendado) Hacer un clon fresco para la operación
# git clone <repo-url> repo-clean
# cd repo-clean

# 3. Ejecutar el filtro para eliminar un archivo (si el secreto estaba en un archivo dedicado)
git filter-repo --invert-paths --path path/to/leaked-file.py

# O para reemplazar texto específico en todo el historial (más seguro)
git filter-repo --replace-text <(echo "THE_LEAKED_SECRET==>REDACTED")

# 4. Forzar el push para sobreescribir la historia en el remoto
git push origin main --force
```

**Advertencia**: Reescribir el historial es una operación destructiva. Todos los colaboradores deberán hacer un `git pull --rebase` o un clon fresco de sus repositorios locales.

### Paso 4: Actualizar la configuración local

Actualiza tu archivo `.env` local con las nuevas credenciales generadas en el Paso 1. **No comitees este archivo.**

### Paso 5: Notificar

Informa a todos los colaboradores del proyecto sobre el incidente y las acciones tomadas, especialmente sobre la necesidad de actualizar sus repositorios locales debido a la reescritura del historial.