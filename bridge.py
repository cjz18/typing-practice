"""Qt window for typing practice. Lyric lines stay on one layer."""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Property, Signal, Slot
from PySide6.QtGui import QColor, QFontDatabase, QKeyEvent
from PySide6.QtWidgets import QColorDialog, QFileDialog

import books
from engine import Session
from icons import icon_dir
from product import APP_NAME, progress_path
from texts import build_passage, choose, read_text_file, split_segments

BG = "#1a1b26"
FG = "#c0caf5"
FRAME_RATES = (30, 60, 120, 240)
COVERS = ("#5c4d8a", "#2f5d62", "#8a4a3c", "#3d5a80", "#6d4c3b", "#3e5c49", "#7a3e5c", "#3a4a6b")


class Bridge(QObject):
    updated = Signal()
    scroll = Signal()
    shiftReset = Signal()
    libraryChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.check_punct = True
        self.show_pinyin = False
        self.fps = 60
        self.bg = BG
        self.fg = FG
        self.page = "practice"
        self.return_page = "practice"
        self.menu_open = False
        self.note = ""
        self.status = ""
        self.imported: list[str] | None = None
        self.import_pos = 0
        self.book_id: str | None = None
        self.source_kind = "builtin"
        self.source_path: str | None = None
        self.source_text: str | None = None
        self.last_score: tuple[float, float, int, str] | None = None
        self.scrolling = False
        self.dialog = False
        self.session = Session(build_passage(choose("en")), True)
        self.pinyin_font = _load_inter()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)
        self._restore()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.KeyPress or self.dialog:
            return False
        return self._on_key(event)

    def _on_key(self, event: QKeyEvent) -> bool:
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            return False
        if self.page == "settings":
            if event.key() == Qt.Key.Key_Escape:
                self.closeSettings()
            return True
        if self.page == "library":
            if event.key() == Qt.Key.Key_Escape:
                self.showPractice()
            return True
        if event.key() == Qt.Key.Key_Escape and self.menu_open:
            self.menu_open = False
            self.updated.emit()
            return True
        if self.scrolling:
            self.finishScroll()
        if event.key() == Qt.Key.Key_Backspace:
            self.note = ""
            self.session.backspace()
            self._publish()
            return True
        text = event.text()
        if not text or ord(text) < 32:
            return False
        if self.menu_open:
            self.menu_open = False
        self.note = ""
        was_finished = self.session.finished
        for char in text:
            self.session.press(char)
        if not was_finished and self.session.finished:
            self._advance()
        else:
            self._publish()
        return True

    def _advance(self) -> None:
        self._capture_score()
        if self.imported is not None and self.import_pos + 1 < len(self.imported):
            self.scrolling = True
            self.updated.emit()
            self.scroll.emit()
            return
        if self.imported is not None and self.book_id:
            book = books.get_book(self.book_id)
            title = book.title if book else "这本书"
            books.mark_finished(self.book_id)
            self.book_id = None
            self.imported = None
            self.note = ""
            self._start_builtin(self.session.passage.mode)
            self.status = f"已读完《{title}》"
            self.page = "library"
            self._refresh_library()
            self.updated.emit()
            return
        if self.imported is not None:
            mode = self.session.passage.mode
            self.imported = None
            self.note = "已练完导入文本，回到内置短句"
            self._start_builtin(mode)
            return
        self.note = ""
        self._start_builtin(self.session.passage.mode)

    @Slot()
    def finishScroll(self) -> None:
        if not self.scrolling:
            return
        self.scrolling = False
        if self.imported is not None and self.import_pos + 1 < len(self.imported):
            self.import_pos += 1
            self._start_sentence(self.imported[self.import_pos])
        self.shiftReset.emit()

    def _start_sentence(self, text: str) -> None:
        self.session = Session(build_passage(text), self.check_punct)
        self._save()
        self._publish()

    def _start_builtin(self, mode: str) -> None:
        avoid = self.session.passage.text if self.session.passage.mode == mode else None
        self.imported = None
        self.book_id = None
        self.source_kind = "builtin"
        self.source_path = None
        self.source_text = None
        self._start_sentence(choose(mode, avoid))

    def _capture_score(self) -> None:
        if self.session.started_at is None:
            return
        self.last_score = (
            self.session.speed(),
            self.session.accuracy,
            self.session.errors,
            self.session.passage.mode,
        )

    def _publish(self) -> None:
        self._save()
        self.updated.emit()

    def _tick(self) -> None:
        if self.session.started_at is not None and not self.session.finished and not self.scrolling:
            self.updated.emit()

    # --- lines -----------------------------------------------------------------

    def _line(self, offset: int) -> str:
        if self.imported is None:
            return ""
        index = self.import_pos + offset
        if index < 0 or index >= len(self.imported):
            return ""
        return self.imported[index]

    def _chars(self) -> list[dict]:
        rows = []
        for index, unit in enumerate(self.session.passage.units):
            if unit.kind == "punct" and not self.session.check_punctuation:
                state = "skip"
            elif index < self.session.index:
                state = "done"
            elif index == self.session.index:
                state = "error" if self.session.error else "current"
            else:
                state = "pending"
            rows.append({"t": unit.display, "s": state})
        return rows

    def _mix(self, amount: float) -> str:
        def channel(color: str, index: int) -> int:
            return int(color[index : index + 2], 16)

        mixed = []
        for index in (1, 3, 5):
            value = channel(self.fg, index) + (channel(self.bg, index) - channel(self.fg, index)) * amount
            mixed.append(f"{round(value):02x}")
        return "#" + "".join(mixed)

    def _current_html(self) -> str:
        parts = []
        for row in self._chars():
            state = row["s"]
            if state == "error":
                color = "#f7768e"
            elif state == "current":
                color = self.fg
            elif state == "done":
                color = self._mix(0.28)
            else:
                color = self._mix(0.62)
            text = row["t"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f'<font color="{color}">{text}</font>')
        return "".join(parts)

    def _hint(self) -> str:
        unit = self.session.current_unit()
        if self.session.error and unit is not None and self.session.typed is not None:
            expected = unit.keys[len(self.session.typed) : len(self.session.typed) + 1]
            return f"按了 {_key_name(self.session.wrong)}，应为 {_key_name(expected)}"
        return ""

    def _pinyin(self) -> tuple[str, str]:
        unit = self.session.current_unit()
        if unit is None or unit.kind != "hanzi":
            return "", ""
        typed = self.session.typed
        rest = unit.keys[len(typed) :]
        if not self.show_pinyin:
            rest = ""
        return typed, rest

    def _stats(self) -> str:
        show_previous = self.last_score is not None and self.session.started_at is None
        if show_previous and self.last_score is not None:
            value, accuracy, errors, mode = self.last_score
            prefix = "上一句 "
        else:
            value = self.session.speed()
            if (
                self.session.started_at is not None
                and not self.session.finished
                and time.perf_counter() - self.session.started_at < 0.5
            ):
                value = 0
            accuracy = self.session.accuracy
            errors = self.session.errors
            mode = self.session.passage.mode
            prefix = ""
        unit = "WPM" if mode == "en" else "字/分钟"
        return f"{prefix}{round(value)} {unit} · {round(accuracy)}% · 错误 {errors}"

    def _place(self) -> str:
        if self.imported is None:
            return ""
        position = f"{self.import_pos + 1} / {len(self.imported)}"
        if self.book_id:
            book = books.get_book(self.book_id)
            if book is not None:
                return f"{book.title} · {position}"
        if self.source_kind == "file" and self.source_path:
            from pathlib import Path

            return f"{Path(self.source_path).stem} · {position}"
        return position

    # --- navigation ------------------------------------------------------------

    @Slot()
    def toggleMenu(self) -> None:
        self.menu_open = not self.menu_open
        self.updated.emit()

    @Slot(str)
    def useMode(self, mode: str) -> None:
        if self.imported is None and self.session.passage.mode == mode:
            self.menu_open = False
            self.updated.emit()
            return
        self.last_score = None
        self.note = ""
        self.menu_open = False
        self.page = "practice"
        self._start_builtin(mode)

    @Slot()
    def restart(self) -> None:
        self.last_score = None
        self.note = ""
        self.session = Session(self.session.passage, self.check_punct)
        self.menu_open = False
        self._publish()

    @Slot()
    def nextPiece(self) -> None:
        self.menu_open = False
        if self.scrolling:
            self.finishScroll()
        self._advance()

    @Slot()
    def showLibrary(self) -> None:
        self.menu_open = False
        self.page = "library"
        self._refresh_library()
        self.updated.emit()

    @Slot()
    def showPractice(self) -> None:
        self.page = "practice"
        self.note = ""
        self.updated.emit()

    @Slot()
    def showSettings(self) -> None:
        self.return_page = self.page
        self.menu_open = False
        self.page = "settings"
        self.updated.emit()

    @Slot()
    def closeSettings(self) -> None:
        self.page = "library" if self.return_page == "library" else "practice"
        self.updated.emit()

    @Slot(bool)
    def setPunct(self, enabled: bool) -> None:
        if enabled == self.check_punct:
            return
        self.check_punct = enabled
        self.restart()

    @Slot(bool)
    def setPinyin(self, enabled: bool) -> None:
        if enabled == self.show_pinyin:
            return
        self.show_pinyin = enabled
        self._publish()

    @Slot(int)
    def setFps(self, fps: int) -> None:
        if fps in FRAME_RATES:
            self.fps = fps
            self._save()
            self.updated.emit()

    @Slot(str)
    def pickColor(self, kind: str) -> None:
        current = QColor(self.bg if kind == "bg" else self.fg)
        self.dialog = True
        chosen = QColorDialog.getColor(current, None, "背景" if kind == "bg" else "字体颜色")
        self.dialog = False
        if not chosen.isValid():
            return
        if kind == "bg":
            self.bg = chosen.name()
        else:
            self.fg = chosen.name()
        self._save()
        self.updated.emit()

    @Slot()
    def restoreDefaults(self) -> None:
        punct_changed = not self.check_punct
        self.bg = BG
        self.fg = FG
        self.show_pinyin = False
        self.fps = 60
        self.check_punct = True
        if punct_changed:
            self.restart()
        else:
            self._publish()

    @Slot()
    def paste(self) -> None:
        from PySide6.QtWidgets import QApplication

        text = QApplication.clipboard().text()
        self.menu_open = False
        if not str(text).strip():
            self.note = "剪贴板是空的"
            self.updated.emit()
            return
        self.last_score = None
        self._load_imported(str(text), 0, None, None)

    @Slot()
    def pickFiles(self) -> None:
        self.dialog = True
        paths, _ = QFileDialog.getOpenFileNames(None, "加入资料库", "", "文本文件 (*.txt);;所有文件 (*.*)")
        self.dialog = False
        if paths:
            self.addPaths(paths)

    @Slot(list)
    def addPaths(self, paths: list) -> None:
        added = 0
        existing = 0
        for raw in paths:
            path = raw.toLocalFile() if hasattr(raw, "toLocalFile") else str(raw)
            if path.startswith("file:"):
                path = QUrl(path).toLocalFile()
            if not path.lower().endswith(".txt"):
                continue
            try:
                _book, created = books.add_file(path)
            except (OSError, ValueError):
                continue
            if created:
                added += 1
            else:
                existing += 1
        if added:
            self.status = f"已加入 {added} 本" if added > 1 else "已加入"
        elif existing:
            self.status = "已经在资料库里"
        self.page = "library"
        self._refresh_library()
        self.updated.emit()

    @Slot(str)
    def openBook(self, book_id: str) -> None:
        book = books.get_book(book_id)
        if book is None:
            return
        try:
            text = books.read_text(book_id)
        except OSError:
            self.status = "这本书的文件读不出来"
            self.updated.emit()
            return
        index = 0 if book.finished else book.index
        self.last_score = None
        self.page = "practice"
        self._load_imported(text, index, str(books.book_file(book_id)), book_id)

    @Slot(str)
    def removeBook(self, book_id: str) -> None:
        books.remove_book(book_id)
        if self.book_id == book_id:
            self.book_id = None
            self.imported = None
            self._start_builtin(self.session.passage.mode)
        self.status = "已从资料库移除"
        self._refresh_library()
        self.updated.emit()

    def _load_imported(self, text: str, index: int, path: str | None, book_id: str | None) -> None:
        segments = split_segments(text)
        if not segments:
            self.note = "没有可练习的文本"
            self.updated.emit()
            return
        self.imported = segments
        self.import_pos = max(0, min(index, len(segments) - 1))
        self.book_id = book_id
        if path:
            self.source_kind = "file"
            self.source_path = path
            self.source_text = None
        else:
            self.source_kind = "paste"
            self.source_path = None
            self.source_text = text
        self.note = ""
        self._start_sentence(segments[self.import_pos])

    def _refresh_library(self) -> None:
        self.libraryChanged.emit()

    def _library_rows(self) -> list[dict]:
        rows = []
        for book in books.list_books():
            if book.finished:
                caption = "读完"
                ratio = 1.0
            elif book.opened and book.segments:
                caption = f"{min(book.index + 1, book.segments)} / {book.segments}"
                ratio = (book.index + 1) / book.segments
            else:
                caption = ""
                ratio = 0.0
            rows.append(
                {
                    "id": book.id,
                    "title": book.title,
                    "caption": caption,
                    "ratio": ratio,
                    "color": COVERS[sum(ord(char) for char in book.id) % len(COVERS)],
                }
            )
        return rows

    # --- progress --------------------------------------------------------------

    def _save(self) -> None:
        payload = {
            "kind": self.source_kind,
            "index": self.import_pos if self.imported is not None else 0,
            "mode": self.session.passage.mode,
            "sentence": self.session.passage.text,
            "check_punctuation": self.check_punct,
            "show_pinyin": self.show_pinyin,
            "fps": self.fps,
            "bg": self.bg,
            "fg": self.fg,
        }
        if self.book_id:
            payload["book_id"] = self.book_id
        if self.source_kind == "file" and self.source_path:
            payload["path"] = self.source_path
        elif self.source_kind == "paste":
            payload["text"] = self.source_text or ""
        try:
            progress_path().write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            return
        if self.book_id and self.imported is not None:
            try:
                books.update_progress(self.book_id, self.import_pos, len(self.imported), False)
            except OSError:
                return

    def _restore(self) -> None:
        try:
            data = json.loads(progress_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return
        if not isinstance(data, dict):
            return
        self.check_punct = bool(data.get("check_punctuation", True))
        self.show_pinyin = bool(data.get("show_pinyin", False))
        if data.get("fps") in FRAME_RATES:
            self.fps = int(data["fps"])
        if _hex_ok(str(data.get("bg") or "")):
            self.bg = str(data["bg"])
        if _hex_ok(str(data.get("fg") or "")):
            self.fg = str(data["fg"])
        kind = data.get("kind")
        mode = data.get("mode") if data.get("mode") in ("en", "zh") else "en"
        if kind == "file":
            path = str(data.get("path") or "")
            book_id = str(data.get("book_id") or "")
            if book_id and books.get_book(book_id) is not None:
                path = str(books.book_file(book_id))
            else:
                book_id = ""
            try:
                content = read_text_file(path)
            except OSError:
                self.note = "找不到上次的文件，已从内置短句开始"
                self._start_builtin(mode)
                return
            if not book_id and path:
                try:
                    adopted, _created = books.add_file(path)
                    book_id = adopted.id
                    path = str(books.book_file(book_id))
                except (OSError, ValueError):
                    book_id = ""
            self._load_imported(content, _index(data.get("index")), path, book_id or None)
            return
        if kind == "paste":
            text = str(data.get("text") or "")
            if text.strip():
                self._load_imported(text, _index(data.get("index")), None, None)
                return
        if kind == "builtin":
            sentence = str(data.get("sentence") or "").strip()
            if sentence:
                self.imported = None
                self._start_sentence(sentence)
                self.session = Session(build_passage(sentence, mode), self.check_punct)

    def _get(self, name: str):
        return getattr(self, name)

    pageName = Property(str, lambda self: self.page, notify=updated)
    background = Property(str, lambda self: self.bg, notify=updated)
    foreground = Property(str, lambda self: self.fg, notify=updated)
    menuOpen = Property(bool, lambda self: self.menu_open, notify=updated)
    modeName = Property(str, lambda self: self.session.passage.mode, notify=updated)
    prevLine = Property(str, lambda self: self._line(-1), notify=updated)
    currentLine = Property(str, lambda self: self.session.passage.text, notify=updated)
    nextLine = Property(str, lambda self: self._line(1), notify=updated)
    afterLine = Property(str, lambda self: self._line(2), notify=updated)
    beforeLine = Property(str, lambda self: self._line(-2), notify=updated)
    chars = Property(list, lambda self: self._chars(), notify=updated)
    currentHtml = Property(str, lambda self: self._current_html(), notify=updated)
    pinyinTyped = Property(str, lambda self: self._pinyin()[0], notify=updated)
    pinyinRest = Property(str, lambda self: self._pinyin()[1], notify=updated)
    errorText = Property(str, lambda self: self._hint(), notify=updated)
    statsText = Property(str, lambda self: self._stats(), notify=updated)
    placeText = Property(str, lambda self: self._place(), notify=updated)
    noteText = Property(str, lambda self: self.note or self.status, notify=updated)
    scrollingNow = Property(bool, lambda self: self.scrolling, notify=updated)
    punctOn = Property(bool, lambda self: self.check_punct, notify=updated)
    pinyinOn = Property(bool, lambda self: self.show_pinyin, notify=updated)
    frameRate = Property(int, lambda self: self.fps, notify=updated)
    chinese = Property(bool, lambda self: self.session.passage.mode == "zh", notify=updated)
    libraryRows = Property(list, lambda self: self._library_rows(), notify=libraryChanged)
    pinyinFont = Property(str, lambda self: self.pinyin_font, notify=updated)

    @Slot(str, result=str)
    def iconUrl(self, name: str) -> str:
        return QUrl.fromLocalFile(str(icon_dir() / f"{name}-light.svg")).toString()


def _load_inter() -> str:
    from pathlib import Path
    import sys

    path = Path(__file__).resolve().parent / "assets" / "fonts" / "InterVariable.ttf"
    if getattr(sys, "frozen", False):
        path = Path(getattr(sys, "_MEIPASS", "")) / "assets" / "fonts" / "InterVariable.ttf"
    if not path.is_file():
        return "Microsoft YaHei UI"
    font_id = QFontDatabase.addApplicationFont(str(path))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    return families[0] if families else "Microsoft YaHei UI"


def _hex_ok(value: str) -> bool:
    text = value.strip().lower()
    if len(text) != 7 or not text.startswith("#"):
        return False
    try:
        int(text[1:], 16)
    except ValueError:
        return False
    return True


def _index(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _key_name(char: str) -> str:
    if char == " ":
        return "空格"
    return char or ""
