from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendar import authorize
from .browser_ava import BrowserAvaClient
from .config import Settings
from .store import Store
from .sync import synchronize


def _doctor() -> int:
    """Verifica o que é necessário antes de executar no Termux."""
    required = ("AVA_LOGIN_URL", "AVA_ACTIVITIES_URL", "AVA_USERNAME", "AVA_PASSWORD")
    config_dir = Path(os.environ.get("UFMT_AGENT_HOME", "~/.config/ufmt-agent")).expanduser()
    env_file = config_dir / ".env"
    # Settings.load também lê esse arquivo; aqui só evitamos expor valores.
    if env_file.exists():
        from .config import _load_env
        _load_env(env_file)
    missing = [name for name in required if not os.environ.get(name)]
    checks = {
        "configuração": not missing,
        "Termux Job Scheduler": shutil.which("termux-job-scheduler") is not None,
        "token Google": (config_dir / "token.json").is_file(),
    }
    for label, passed in checks.items():
        print(f"{'OK' if passed else 'PENDENTE'}  {label}")
    if missing:
        print("Variáveis ausentes: " + ", ".join(missing))
    return 0 if all(checks.values()) else 1


def _in_window(settings: Settings) -> bool:
    now = datetime.now(ZoneInfo(settings.timezone))
    return now.hour == 7


def _run(settings: Settings, scheduled: bool) -> int:
    if scheduled and not _in_window(settings):
        return 0
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    if scheduled and Store(settings.database_path).ran_successfully_today(settings.timezone):
        return 0
    with open(settings.config_dir / "sync.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        print(synchronize(settings))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ufmt-sync")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("sync")
    sub.add_parser("scheduled")
    sub.add_parser("inspect")
    sub.add_parser("doctor")
    auth = sub.add_parser("authorize")
    auth.add_argument("--client-secret", required=True)
    auth.add_argument("--output", default="token.json")
    sub.add_parser("schedule")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _doctor()
    if args.command == "authorize":
        authorize(args.client_secret, args.output)
        return 0
    settings = Settings.load()
    if args.command == "inspect":
        print(BrowserAvaClient(settings).inspect())
        return 0
    if args.command == "schedule":
        # A CLI é instalada dentro do venv, portanto __file__ aponta para
        # site-packages e não para a cópia do projeto. Criamos um lançador
        # estável no diretório de configuração usando o mesmo Python do venv.
        script = settings.config_dir / "run_scheduled.py"
        script.write_text(
            f"#!{sys.executable}\nfrom ufmt_agent.cli import main\nraise SystemExit(main(['scheduled']))\n",
            encoding="utf-8",
        )
        script.chmod(0o700)
        subprocess.run(["termux-job-scheduler", "--script", str(script), "--job-id", "271", "--period-ms", "900000", "--network", "any", "--battery-not-low", "true", "--persisted", "true"], check=True)
        return 0
    return _run(settings, scheduled=args.command == "scheduled")


if __name__ == "__main__":
    sys.exit(main())
