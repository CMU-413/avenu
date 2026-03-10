from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, jsonify

from services.health_service import DEPENDENCY_ORDER, HEALTHY, UNREACHABLE, HealthService

health_bp = Blueprint("health", __name__)


def _normalize_dependency_map(raw_statuses: dict[str, str]) -> OrderedDict[str, str]:
    normalized: OrderedDict[str, str] = OrderedDict()
    for dependency in DEPENDENCY_ORDER:
        normalized[dependency] = raw_statuses.get(dependency, UNREACHABLE)
    return normalized


@health_bp.route("/api/health", methods=["GET"])
def health_liveness_route():
    return jsonify({"status": "ok"}), 200


@health_bp.route("/api/health/dependencies", methods=["GET"])
def health_dependencies_route():
    raw_statuses = HealthService().check_dependencies()
    statuses = _normalize_dependency_map(raw_statuses=raw_statuses)
    code = 200 if all(status == HEALTHY for status in statuses.values()) else 503
    return jsonify(statuses), code
