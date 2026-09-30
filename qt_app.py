"""Launch the Qt typing window."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtQml import QQmlApplicationEngine

from bridge import Bridge
from product import APP_NAME, log_path


def main() -> int:
    notes: list[str] = []

    def remember(_mode, _context, message) -> None:
        notes.append(str(message))

    qInstallMessageHandler(remember)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Microsoft YaHei UI", 11))
    try:
        bridge = Bridge()
    except Exception as exc:
        _fail(app, f"{type(exc).__name__}: {exc}")
        return 1
    app.installEventFilter(bridge)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    qml = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        _fail(app, "\n".join(notes) or "界面没有打开")
        return 1
    return app.exec()


def _fail(app: QApplication, detail: str) -> None:
    try:
        log_path().write_text(detail, encoding="utf-8")
    except OSError:
        pass
    QMessageBox.critical(None, APP_NAME, "打字练习没有打开。\n\n" + detail[:1200])


if __name__ == "__main__":
    raise SystemExit(main())
