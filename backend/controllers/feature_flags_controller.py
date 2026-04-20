from __future__ import annotations

from flask import Blueprint, jsonify

from config import get_feature_flags

feature_flags_bp = Blueprint("feature_flags", __name__)


@feature_flags_bp.route("/api/feature-flags", methods=["GET"])
def list_feature_flags():
    return jsonify(get_feature_flags()), 200
