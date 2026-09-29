"""Product identity and per-user storage."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "打字练习"
APP_VERSION = "1.0.0"
APP_SUMMARY = "英文打字与中文拼音练习。进度只保存在本机。"


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home()
    folder = root / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def progress_path() -> Path:
    target = user_data_dir() / "progress.json"
    legacy = install_dir() / "progress.json"
    if not target.exists() and legacy.exists() and legacy.resolve() != target.resolve():
        try:
            target.write_bytes(legacy.read_bytes())
        except OSError:
            return target
    return target


def log_path() -> Path:
    return user_data_dir() / "app.log"
