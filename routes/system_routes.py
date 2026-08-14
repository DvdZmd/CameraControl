"""Contrato de composición y capacidades de la instancia activa."""

from flask import Blueprint, current_app, jsonify


system_bp = Blueprint("system", __name__, url_prefix="/api/system")


@system_bp.route("/capabilities", methods=["GET"])
def capabilities():
    profile = current_app.config["PROJECT_PROFILE"]
    return jsonify({
        "api_version": "1",
        "profile": profile.name,
        "features": profile.features.as_dict(),
    })
