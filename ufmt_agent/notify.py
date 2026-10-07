from __future__ import annotations

import shutil
import subprocess


def notify(title: str, content: str) -> None:
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", content], check=False)
    else:
        print(f"{title}: {content}")
