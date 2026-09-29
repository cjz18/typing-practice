"""Local bookshelf. Imported texts are copied here and keep their own progress."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from product import user_data_dir
from texts import read_text_file, split_segments


@dataclass
class Book:
    id: str
    title: str
    digest: str
    added: float
    index: int
    segments: int
    finished: bool
    opened: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "digest": self.digest,
            "added": self.added,
            "index": self.index,
            "segments": self.segments,
            "finished": self.finished,
            "opened": self.opened,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Book | None:
        book_id = str(data.get("id") or "").strip()
        title = str(data.get("title") or "").strip()
        if not book_id or not title:
            return None
        try:
            index = max(0, int(data.get("index") or 0))
            segments = max(0, int(data.get("segments") or 0))
            added = float(data.get("added") or 0)
        except (TypeError, ValueError):
            return None
        finished = bool(data.get("finished"))
        opened = bool(data.get("opened") or index or finished)
        return cls(
            id=book_id,
            title=title,
            digest=str(data.get("digest") or ""),
            added=added,
            index=index,
            segments=segments,
            finished=finished,
            opened=opened,
        )


def books_dir() -> Path:
    folder = user_data_dir() / "books"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def book_file(book_id: str) -> Path:
    return books_dir() / f"{book_id}.txt"


def _index_path() -> Path:
    return user_data_dir() / "library.json"


def list_books() -> list[Book]:
    books = _load()
    books.sort(key=lambda book: book.added, reverse=True)
    return books


def get_book(book_id: str) -> Book | None:
    for book in _load():
        if book.id == book_id:
            return book
    return None


def read_text(book_id: str) -> str:
    return read_text_file(str(book_file(book_id)))


def add_file(path: str) -> tuple[Book, bool]:
    file = Path(path)
    if file.parent.resolve() == books_dir().resolve():
        existing = get_book(file.stem)
        if existing is not None:
            return existing, False
    return add_text(file.stem or "未命名", read_text_file(str(file)))


def add_text(title: str, text: str) -> tuple[Book, bool]:
    segments = split_segments(text)
    if not segments:
        raise ValueError("empty")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    for book in _load():
        if book.digest == digest:
            return book, False
    book = Book(
        id=uuid.uuid4().hex[:12],
        title=title.strip() or "未命名",
        digest=digest,
        added=time.time(),
        index=0,
        segments=len(segments),
        finished=False,
        opened=False,
    )
    book_file(book.id).write_text(text, encoding="utf-8")
    books = _load()
    books.append(book)
    _save(books)
    return book, True


def update_progress(book_id: str, index: int, segments: int, finished: bool) -> None:
    books = _load()
    changed = False
    for book in books:
        if book.id != book_id:
            continue
        book.index = max(0, index)
        book.segments = max(segments, 1)
        book.finished = finished
        book.opened = True
        changed = True
        break
    if changed:
        _save(books)


def mark_finished(book_id: str) -> None:
    book = get_book(book_id)
    if book is None:
        return
    update_progress(book_id, book.segments, book.segments, True)


def remove_book(book_id: str) -> None:
    books = [book for book in _load() if book.id != book_id]
    _save(books)
    try:
        book_file(book_id).unlink(missing_ok=True)
    except OSError:
        return


def _load() -> list[Book]:
    try:
        raw = json.loads(_index_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return []
    if not isinstance(raw, dict):
        return []
    found = []
    for item in raw.get("books") or []:
        if not isinstance(item, dict):
            continue
        book = Book.from_dict(item)
        if book is not None and book_file(book.id).is_file():
            found.append(book)
    return found


def _save(books: list[Book]) -> None:
    payload = {"books": [book.to_dict() for book in books]}
    _index_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
