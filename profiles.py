"""Perfiles de producto y capacidades habilitadas en CameraControl."""

from dataclasses import asdict, dataclass
import os


@dataclass(frozen=True)
class FeatureConfig:
    """Módulos que componen una instancia de CameraControl."""

    camera: bool = True
    timelapse: bool = True
    esp32: bool = True
    pan_tilt: bool = True
    lighting: bool = True
    sensors: bool = True
    tuya: bool = True

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectProfile:
    """Identidad de producto y composición del backend."""

    name: str
    features: FeatureConfig

    def validate(self) -> None:
        errors = []
        if self.features.timelapse and not self.features.camera:
            errors.append("timelapse requiere camera")
        if self.features.sensors and not self.features.esp32:
            errors.append("sensors requiere esp32")
        if self.features.pan_tilt and not self.features.esp32:
            errors.append("pan_tilt requiere esp32")
        if self.features.lighting and not self.features.esp32:
            errors.append("lighting requiere esp32")
        if errors:
            raise ValueError(
                f"Perfil CameraControl inválido '{self.name}': {', '.join(errors)}"
            )

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "features": self.features.as_dict()}


PROFILES = {
    # Compatibilidad: si no se selecciona un perfil, todos los módulos actuales
    # permanecen habilitados.
    "default": ProjectProfile("default", FeatureConfig()),
    "starseek": ProjectProfile(
        "starseek",
        FeatureConfig(lighting=False, sensors=False, tuya=False),
    ),
    "fungiforge": ProjectProfile("fungiforge", FeatureConfig()),
    "fungiforge_monitor": ProjectProfile(
        "fungiforge_monitor",
        FeatureConfig(pan_tilt=False),
    ),
}


def resolve_profile(profile_name: str | None = None) -> ProjectProfile:
    """Resuelve y valida un perfil explícito o configurado por entorno."""

    selected_name = profile_name or os.environ.get("CAMERACONTROL_PROFILE", "default")
    selected_name = selected_name.strip().lower()
    try:
        profile = PROFILES[selected_name]
    except KeyError as error:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Perfil CameraControl desconocido '{selected_name}'. "
            f"Perfiles disponibles: {available}"
        ) from error
    profile.validate()
    return profile
