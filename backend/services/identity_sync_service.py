from __future__ import annotations

from typing import Any

import requests

from errors import APIError
from repositories.teams_repository import ensure_team_from_external_identity
from repositories.users_repository import upsert_user_from_external_identity


OPTIX_GRAPHQL_ENDPOINT = "https://api.optixapp.com/graphql"
OPTIX_ME_QUERY = """
query {
  me {
    user {
      user_id
      email
      fullname
      phone
      is_admin
      teams {
        team_id
        name
      }
    }
  }
}
"""


def check_optix_health(*, token: str, timeout_seconds: float = 1.0) -> str:
    normalized_token = token.strip()
    if not normalized_token:
        return "misconfigured"

    try:
        response = requests.post(
            OPTIX_GRAPHQL_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {normalized_token}",
            },
            json={"query": "query { me { user { user_id } } }"},
            timeout=timeout_seconds,
        )
    except requests.Timeout:
        return "unreachable"
    except requests.RequestException:
        return "unreachable"

    if response.status_code in {401, 403}:
        return "misconfigured"
    if response.status_code != 200:
        return "error"

    return "healthy"


def _coerce_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise APIError(422, f"{field_name} must be a positive integer")
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            value = int(value)
    if not isinstance(value, int) or value < 1:
        raise APIError(422, f"{field_name} must be a positive integer")
    return value


def sync_optix_identity(*, token: str) -> tuple[bool, dict[str, Any]]:
    response = requests.post(
        OPTIX_GRAPHQL_ENDPOINT,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json={"query": OPTIX_ME_QUERY},
    )

    if response.status_code != 200:
        raise APIError(response.status_code, "Failed to query Optix API")

    data = response.json()
    user_info = data.get("data", {}).get("me", {}).get("user", {})
    if not user_info:
        raise APIError(400, "No user info returned from Optix")

    optix_user_id = _coerce_positive_int(user_info.get("user_id"), field_name="user_id")

    team_ids = []
    for team in user_info.get("teams", []):
        optix_team_id = _coerce_positive_int(team.get("team_id"), field_name="team_id")
        team_doc = ensure_team_from_external_identity(optix_id=optix_team_id, name=team.get("name", ""))
        team_ids.append(team_doc["_id"])

    user_doc, created = upsert_user_from_external_identity(
        optix_id=optix_user_id,
        fullname=user_info.get("fullname", ""),
        email=user_info.get("email", ""),
        phone=user_info.get("phone", ""),
        is_admin=bool(user_info.get("is_admin", False)),
        team_ids=team_ids,
    )
    return created, user_doc
