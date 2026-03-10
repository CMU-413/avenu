from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from services.notifications.providers.email_provider import EmailProvider, MailProviderError


class MSGraphEmailProvider(EmailProvider):
    GRAPH_SCOPE = "https://graph.microsoft.com/.default"
    SYNTHETIC_MESSAGE_ID = "msgraph-accepted"
    TOKEN_EXPIRY_SKEW_SECONDS = 60

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        sender_email: str,
        token_url_base: str = "https://login.microsoftonline.com",
        graph_base_url: str = "https://graph.microsoft.com",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._tenant_id = self._require_value("MS_GRAPH_TENANT_ID", tenant_id)
        self._client_id = self._require_value("MS_GRAPH_CLIENT_ID", client_id)
        self._client_secret = self._require_value("MS_GRAPH_CLIENT_SECRET", client_secret)
        self._sender_email = self._require_value("MS_GRAPH_SENDER_EMAIL", sender_email)
        self._token_url_base = token_url_base.rstrip("/")
        self._graph_base_url = graph_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    def send(self, *, to: str, subject: str, html: str) -> str:
        token = self._get_access_token()
        send_url = f"{self._graph_base_url}/v1.0/users/{self._sender_email}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": html,
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to,
                        }
                    }
                ],
            },
            "saveToSentItems": "false",
        }
        body = json.dumps(payload).encode("utf-8")
        status_code, response_body = self._perform_request(
            method="POST",
            url=send_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=body,
        )
        if status_code != 202:
            raise MailProviderError(f"MS Graph sendMail failed status={status_code} body={response_body[:300]}")
        return self.SYNTHETIC_MESSAGE_ID

    def check_health(self, *, timeout_seconds: float) -> str:
        original_timeout = self._timeout_seconds
        self._timeout_seconds = timeout_seconds
        try:
            _ = self._get_access_token()
            return "healthy"
        except MailProviderError as exc:
            message = str(exc).lower()
            if "is required" in message or "status=401" in message or "status=403" in message:
                return "misconfigured"
            if "request failed" in message or "timed out" in message or "timeout" in message:
                return "unreachable"
            return "error"
        except Exception:
            return "error"
        finally:
            self._timeout_seconds = original_timeout

    def _get_access_token(self) -> str:
        now = datetime.now(tz=timezone.utc)
        if self._access_token and self._access_token_expires_at and now < self._access_token_expires_at:
            return self._access_token

        token_url = f"{self._token_url_base}/{self._tenant_id}/oauth2/v2.0/token"
        body = urlencode(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self.GRAPH_SCOPE,
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")

        status_code, response_body = self._perform_request(
            method="POST",
            url=token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=body,
        )
        if status_code != 200:
            raise MailProviderError(f"MS Graph token request failed status={status_code} body={response_body[:300]}")

        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise MailProviderError("MS Graph token response is not valid JSON") from exc

        token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(token, str) or not token:
            raise MailProviderError("MS Graph token response missing access_token")
        if not isinstance(expires_in, int):
            raise MailProviderError("MS Graph token response missing expires_in")

        valid_for = max(1, expires_in - self.TOKEN_EXPIRY_SKEW_SECONDS)
        self._access_token = token
        self._access_token_expires_at = now + timedelta(seconds=valid_for)
        return token

    def _perform_request(self, *, method: str, url: str, headers: dict[str, str], data: bytes) -> tuple[int, str]:
        request = Request(url=url, data=data, method=method)
        for name, value in headers.items():
            request.add_header(name, value)

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return response.getcode(), response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, body
        except URLError as exc:
            raise MailProviderError(f"MS Graph request failed url={url}: {exc}") from exc

    def _require_value(self, env_name: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise MailProviderError(f"{env_name} is required")
        return normalized
