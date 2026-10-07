from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _reminder_minutes(value: str) -> tuple[int, ...]:
    """Converte minutos antes do prazo em uma configuração estável."""
    try:
        minutes = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}, reverse=True))
    except ValueError as exc:
        raise ValueError("UFMT_REMINDER_MINUTES deve conter minutos separados por vírgula") from exc
    if any(item <= 0 for item in minutes):
        raise ValueError("UFMT_REMINDER_MINUTES deve conter somente valores positivos")
    return minutes


@dataclass(frozen=True)
class Settings:
    config_dir: Path
    login_url: str
    portal_apps_url: str
    academic_home_url: str
    sso_url: str
    ava_entry_url: str
    activities_url: str
    username_field: str
    password_field: str
    username: str
    password: str
    timezone: str
    calendar_name: str
    browser_headless: bool
    browser_executable: str | None
    reminder_minutes: tuple[int, ...]

    @property
    def database_path(self) -> Path:
        return self.config_dir / "state.sqlite3"

    @property
    def token_path(self) -> Path:
        return self.config_dir / "token.json"

    @property
    def client_secret_path(self) -> Path:
        return self.config_dir / "client_secret.json"

    @property
    def browser_profile_path(self) -> Path:
        return self.config_dir / "browser-profile"

    @classmethod
    def load(cls) -> "Settings":
        config_dir = Path(os.environ.get("UFMT_AGENT_HOME", "~/.config/ufmt-agent")).expanduser()
        _load_env(config_dir / ".env")
        needed = ("AVA_LOGIN_URL", "AVA_ACTIVITIES_URL", "AVA_USERNAME", "AVA_PASSWORD")
        missing = [key for key in needed if not os.environ.get(key)]
        if missing:
            raise ValueError("Configuração ausente: " + ", ".join(missing))
        return cls(
            config_dir=config_dir,
            login_url=os.environ["AVA_LOGIN_URL"],
            portal_apps_url=os.environ.get("AVA_PORTAL_APPS_URL", ""),
            academic_home_url=os.environ.get("AVA_ACADEMIC_HOME_URL", ""),
            sso_url=os.environ.get("AVA_SSO_URL", ""),
            ava_entry_url=os.environ.get("AVA_ENTRY_URL", ""),
            activities_url=os.environ["AVA_ACTIVITIES_URL"],
            username_field=os.environ.get("AVA_USERNAME_FIELD", "username"),
            password_field=os.environ.get("AVA_PASSWORD_FIELD", "password"),
            username=os.environ["AVA_USERNAME"],
            password=os.environ["AVA_PASSWORD"],
            timezone=os.environ.get("AVA_TIMEZONE", "America/Cuiaba"),
            calendar_name=os.environ.get("UFMT_CALENDAR_NAME", "UFMT"),
            browser_headless=os.environ.get("UFMT_BROWSER_HEADLESS", "true").casefold() not in {"0", "false", "no"},
            # No Termux usamos o Chromium instalado pelo próprio sistema; no
            # computador o Playwright continua usando seu navegador gerenciado.
            browser_executable=os.environ.get("UFMT_CHROMIUM_EXECUTABLE") or None,
            # 15, 7, 3 e 1 dia antes. O Calendar é responsável por disparar os
            # avisos depois que o evento é criado pelo agente.
            reminder_minutes=_reminder_minutes(os.environ.get("UFMT_REMINDER_MINUTES", "21600,10080,4320,1440")),
        )
