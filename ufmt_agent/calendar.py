from __future__ import annotations

import json
import secrets
import subprocess
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

import requests

from .config import Settings
from .models import Delivery

SCOPES = ["https://www.googleapis.com/auth/calendar"]
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_URL = "https://www.googleapis.com/calendar/v3"


class CalendarClient:
    """Cliente REST do Google Calendar sem dependências binárias no Android."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.token = self._token()
        self.calendar_id = self._calendar_id()

    def _token(self) -> dict:
        if not self.settings.token_path.exists():
            raise RuntimeError("token.json não encontrado; execute o comando authorize")
        token = json.loads(self.settings.token_path.read_text(encoding="utf-8"))
        if self._expired(token.get("expires_at") or token.get("expiry")):
            token.update(self._refresh(token))
            self._save_token(token)
        return token

    @staticmethod
    def _expired(expiry: str | float | int | None) -> bool:
        if not expiry:
            return False
        if isinstance(expiry, (int, float)):
            return float(expiry) <= time.time() + 60
        try:
            return datetime.fromisoformat(expiry.replace("Z", "+00:00")).timestamp() <= time.time() + 60
        except ValueError:
            return True

    def _refresh(self, token: dict) -> dict:
        if not token.get("refresh_token"):
            raise RuntimeError("Token Google expirado sem refresh_token; execute authorize novamente")
        response = requests.post(_TOKEN_URL, data={
            "client_id": token["client_id"], "client_secret": token.get("client_secret", ""),
            "refresh_token": token["refresh_token"], "grant_type": "refresh_token",
        }, timeout=30)
        response.raise_for_status()
        data = response.json()
        data["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        return data

    def _save_token(self, token: dict) -> None:
        self.settings.token_path.write_text(json.dumps(token), encoding="utf-8")
        self.settings.token_path.chmod(0o600)

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token.get('access_token') or self.token.get('token')}"
        response = requests.request(method, _API_URL + path, headers=headers, timeout=30, **kwargs)
        if response.status_code == 401:
            self.token.update(self._refresh(self.token))
            self._save_token(self.token)
            headers["Authorization"] = f"Bearer {self.token['access_token']}"
            response = requests.request(method, _API_URL + path, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    def _calendar_id(self) -> str:
        calendars = self._request("GET", "/users/me/calendarList").json().get("items", [])
        for calendar in calendars:
            if calendar.get("summary") == self.settings.calendar_name:
                return calendar["id"]
        return self._request("POST", "/calendars", json={"summary": self.settings.calendar_name}).json()["id"]

    def _body(self, delivery: Delivery) -> dict:
        body = {
            "summary": f"[{delivery.course}] {delivery.title}",
            "description": f"Sincronizado pelo Agente UFMT.\nOrigem: {delivery.source_url}\n\n{delivery.raw_text}",
            "extendedProperties": {"private": {"ufmt_source_id": delivery.source_id}},
            "reminders": {"useDefault": False, "overrides": [
                {"method": "popup", "minutes": minutes} for minutes in self.settings.reminder_minutes
            ]},
        }
        if delivery.all_day:
            start = delivery.due_at.date()
            body["start"] = {"date": start.isoformat()}
            body["end"] = {"date": (start + timedelta(days=1)).isoformat()}
        else:
            body["start"] = {"dateTime": delivery.due_at.isoformat()}
            body["end"] = {"dateTime": (delivery.due_at + timedelta(minutes=5)).isoformat()}
        return body

    def upsert(self, delivery: Delivery, event_id: str | None) -> tuple[str, str]:
        calendar_id = quote(self.calendar_id, safe="")
        body = self._body(delivery)
        if event_id:
            event = self._request("PUT", f"/calendars/{calendar_id}/events/{quote(event_id, safe='')}", json=body).json()
            return event["id"], "updated"
        event = self._request("POST", f"/calendars/{calendar_id}/events", json=body).json()
        return event["id"], "created"


def authorize(client_secret: str, output: str) -> None:
    client = json.loads(Path(client_secret).read_text(encoding="utf-8")).get("installed")
    if not client:
        raise ValueError("Use um arquivo OAuth do tipo Aplicativo para computador")
    state = secrets.token_urlsafe(24)
    server = HTTPServer(("127.0.0.1", 0), _OAuthCallback)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client["client_id"], "redirect_uri": redirect_uri,
        "response_type": "code", "scope": " ".join(SCOPES),
        "access_type": "offline", "prompt": "consent", "state": state,
    })
    _OAuthCallback.code = _OAuthCallback.error = None
    _OAuthCallback.expected_state = state
    print("Abrindo a autorização do Google no navegador…")
    if subprocess.run(["termux-open-url", url], check=False).returncode != 0:
        webbrowser.open(url)
        print("Se o navegador não abrir, acesse:\n" + url)
    server.timeout = 300
    server.handle_request()
    if _OAuthCallback.error or not _OAuthCallback.code:
        raise RuntimeError("Autorização Google não concluída")
    response = requests.post(_TOKEN_URL, data={
        "code": _OAuthCallback.code, "client_id": client["client_id"],
        "client_secret": client.get("client_secret", ""), "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)
    response.raise_for_status()
    token = response.json()
    token.update({"client_id": client["client_id"], "client_secret": client.get("client_secret", ""), "expires_at": time.time() + int(token.get("expires_in", 3600))})
    output_path = Path(output)
    output_path.write_text(json.dumps(token), encoding="utf-8")
    output_path.chmod(0o600)


class _OAuthCallback(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None
    expected_state: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        query = parse_qs(urlparse(self.path).query)
        if query.get("state", [None])[0] != self.expected_state:
            type(self).error = "Estado OAuth inválido"
        else:
            type(self).code = query.get("code", [None])[0]
            type(self).error = query.get("error", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Autorização concluída. Você pode voltar ao Termux.".encode())

    def log_message(self, format: str, *args) -> None:
        return
