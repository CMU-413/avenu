from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, Response

if TYPE_CHECKING:
    from prometheus_flask_exporter import PrometheusMetrics


def create_metrics_blueprint(prometheus_metrics: PrometheusMetrics) -> Blueprint:
    bp = Blueprint("metrics", __name__)

    @bp.route("/metrics", methods=["GET"])
    def prometheus_metrics_route():
        data, content_type = prometheus_metrics.generate_metrics()
        return Response(data, mimetype=content_type)

    return bp
