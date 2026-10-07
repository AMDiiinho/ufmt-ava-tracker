#!/usr/bin/env python3
"""Ponto de entrada chamado pelo Android JobScheduler."""

import os
from pathlib import Path

project_dir = Path(__file__).resolve().parents[1]
python = project_dir / ".venv" / "bin" / "python"
os.execv(str(python), [str(python), "-m", "ufmt_agent.cli", "scheduled"])
