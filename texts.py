"""Built-in passages and imported-text splitting."""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pypinyin import Style, lazy_pinyin

ENGLISH = [
    "The quick brown fox jumps over the lazy dog.",
    "Practice makes perfect, so keep typing every day.",
    "A journey of a thousand miles begins with a single step.",
    "She sells seashells by the seashore.",
    "Learning to type well saves time and effort.",
    "Please close the door when you leave the room.",
    "Bright stars shine above the quiet mountain lake.",
    "Can you finish this sentence without a mistake?",
    "He read the book, then wrote a short note.",
    "Simple words, typed cleanly, build strong habits.",
    "What time does the morning train arrive?",
    "Keep your wrists straight and your eyes on the screen.",
]

CHINESE = [
    "你好，世界。",
    "今天天气很好。",
    "我喜欢练习打字。",
    "学而时习之，不亦说乎？",
    "春眠不觉晓，处处闻啼鸟。",
    "请把输入法切换到英文。",
    "一心一意把每个字打对。",
    "书山有路勤为径。",
    "早上喝一杯温水吧。",
    "这个问题并不难。",
    "女生在图书馆看书。",
    "祝你打字越来越快！",
]

# Chinese punctuation has no key of its own on an English keyboard.
_PUNCT_KEYS = {
    "。": ".",
    "．": ".",
    "，": ",",
    "、": ",",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "「": '"',
    "」": '"',
    "『": '"',
    "』": '"',
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "〔": "[",
    "〕": "]",
    "《": "<",
    "》": ">",
    "〈": "<",
    "〉": ">",
    "—": "-",
    "–": "-",
    "－": "-",
    "…": "...",
    "⋯": "...",
    "·": "`",
    "～": "~",
    "｡": ".",
    "､": ",",
}

_SENTENCE_BREAK = re.compile(
    r"(?<=[。！？!?；;])\s*|(?<=(?<![.\d])\.)(?=\s|$)\s*"
)
_CLAUSE_BREAK = re.compile(r"(?<=[,，、])(?!\d)\s*|(?<=—)\s*")
_MAX_SEGMENT = 40


@dataclass(frozen=True)
class Unit:
    display: str
    keys: str
    kind: str  # hanzi, char, punct, space


@dataclass(frozen=True)
class Passage:
    text: str
    mode: str
    units: tuple[Unit, ...]


def is_hanzi(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or code == 0x3007
        or 0xF900 <= code <= 0xFAFF
    )


def has_hanzi(text: str) -> bool:
    return any(is_hanzi(char) for char in text)


def classify(char: str) -> str:
    if char.isspace() or unicodedata.category(char).startswith("Z"):
        return "space"
    if unicodedata.category(char).startswith("P"):
        return "punct"
    return "char"


def typing_keys(char: str) -> str:
    mapped = _PUNCT_KEYS.get(char)
    if mapped:
        return mapped
    folded = unicodedata.normalize("NFKC", char)
    if folded != char and folded.isascii() and folded:
        return folded
    if classify(char) == "space":
        return " "
    return char


def _syllables(run: str) -> list[str]:
    pieces = lazy_pinyin(run, style=Style.NORMAL, errors="default")
    if len(pieces) != len(run):
        pieces = []
        for char in run:
            one = lazy_pinyin(char, style=Style.NORMAL, errors="default")
            pieces.append(one[0] if one else char)
    syllables = []
    for char, piece in zip(run, pieces):
        syllable = piece.replace("ü", "v").replace("Ü", "V").lower()
        if syllable.isascii() and syllable.isalpha():
            syllables.append(syllable)
        else:
            syllables.append(char)
    return syllables


def build_passage(text: str, mode: str | None = None) -> Passage:
    text = text.strip()
    if mode is None:
        mode = "zh" if has_hanzi(text) else "en"
    units: list[Unit] = []
    if mode == "en":
        for char in text:
            units.append(Unit(char, typing_keys(char), classify(char)))
    else:
        index = 0
        while index < len(text):
            if is_hanzi(text[index]):
                end = index + 1
                while end < len(text) and is_hanzi(text[end]):
                    end += 1
                run = text[index:end]
                for char, syllable in zip(run, _syllables(run)):
                    if syllable.isascii() and syllable.isalpha():
                        units.append(Unit(char, syllable, "hanzi"))
                    else:
                        units.append(Unit(char, typing_keys(char), classify(char)))
                index = end
                continue
            char = text[index]
            units.append(Unit(char, typing_keys(char), classify(char)))
            index += 1
    return Passage(text, mode, tuple(units))


def choose(mode: str, avoid: str | None = None) -> str:
    pool = CHINESE if mode == "zh" else ENGLISH
    options = [item for item in pool if item != avoid] or list(pool)
    return random.choice(options)


def split_segments(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    segments: list[str] = []
    for paragraph in re.split(r"\n\s*\n", normalized):
        joined = _join_wrapped_lines(paragraph)
        if not joined:
            continue
        for part in _SENTENCE_BREAK.split(joined):
            part = part.strip()
            if part:
                segments.extend(_split_long(part))
    return segments


def _split_long(segment: str) -> list[str]:
    if len(segment) <= _MAX_SEGMENT:
        return [segment]
    parts = [part.strip() for part in _CLAUSE_BREAK.split(segment) if part.strip()]
    if len(parts) <= 1:
        return [segment]
    chunks: list[str] = []
    current = ""
    for part in parts:
        if not current:
            current = part
            continue
        joined = _join_clause(current, part)
        if len(joined) <= _MAX_SEGMENT:
            current = joined
            continue
        chunks.append(current)
        current = part
    if current:
        chunks.append(current)
    return chunks


def _join_clause(left: str, right: str) -> str:
    if is_hanzi(left[-1]) or left[-1] in "，、—" or is_hanzi(right[0]):
        return left + right
    return left + " " + right


def _join_wrapped_lines(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    merged = lines[0]
    for line in lines[1:]:
        if is_hanzi(merged[-1]) or is_hanzi(line[0]):
            merged += line
        else:
            merged += " " + line
    return merged


def read_text_file(path: str) -> str:
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
