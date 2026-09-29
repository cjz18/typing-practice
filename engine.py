"""Typing progress, mistakes, and live speed for one passage."""

from __future__ import annotations

import time

from texts import Passage, Unit


class Session:
    def __init__(self, passage: Passage, check_punctuation: bool = True) -> None:
        self.passage = passage
        self.check_punctuation = check_punctuation
        self.index = 0
        self.typed = ""
        self.error = False
        self.wrong = ""
        self.correct_keys = 0
        self.total_keys = 0
        self.errors = 0
        self.started_at: float | None = None
        self.finished = False
        self.finished_at: float | None = None
        self._skip_punctuation()

    @property
    def completed_hanzi(self) -> int:
        return sum(
            1
            for index, unit in enumerate(self.passage.units)
            if unit.kind == "hanzi" and index < self.index
        )

    @property
    def accuracy(self) -> float:
        if self.total_keys == 0:
            return 100.0
        return 100.0 * self.correct_keys / self.total_keys

    def speed(self, now: float | None = None) -> float:
        """Characters per minute. English uses WPM (5 correct characters = 1 word)."""
        if self.started_at is None:
            return 0.0
        if self.finished and self.finished_at is not None:
            end = self.finished_at
        else:
            end = time.perf_counter() if now is None else now
        elapsed = end - self.started_at
        if elapsed <= 0:
            return 0.0
        minutes = elapsed / 60
        if self.passage.mode == "en":
            return (self.correct_keys / 5) / minutes
        return self.completed_hanzi / minutes

    def current_unit(self) -> Unit | None:
        if self.index >= len(self.passage.units):
            return None
        return self.passage.units[self.index]

    def press(self, char: str) -> None:
        if not char or self.finished:
            return
        self._ensure_started()
        unit = self.current_unit()
        if unit is None:
            self._finish()
            return
        if self._accept_original_character(unit, char):
            self.correct_keys += 1
            self.total_keys += 1
            self.typed = ""
            self.error = False
            self.wrong = ""
            self.index += 1
            self._skip_punctuation()
            return
        expected = unit.keys[len(self.typed)]
        if char == expected:
            self.correct_keys += 1
            self.total_keys += 1
            self.typed += char
            self.error = False
            self.wrong = ""
            if self.typed == unit.keys:
                self.typed = ""
                self.index += 1
                self._skip_punctuation()
            return
        self.total_keys += 1
        self.errors += 1
        self.error = True
        self.wrong = char

    def backspace(self) -> None:
        if self.error:
            self.error = False
            self.wrong = ""
            return
        if self.typed:
            self.typed = self.typed[:-1]
            self._undo_correct_key()
            return
        previous = self._previous_required_index()
        if previous is None:
            return
        if self.finished:
            self.finished = False
            self.finished_at = None
        self.index = previous
        unit = self.passage.units[previous]
        if not unit.keys:
            return
        self.typed = unit.keys[:-1]
        self._undo_correct_key()

    def _accept_original_character(self, unit: Unit, char: str) -> bool:
        # Fullwidth punctuation can be typed as itself. Hanzi still require pinyin.
        return (
            unit.kind != "hanzi"
            and self.typed == ""
            and char == unit.display
            and unit.display != unit.keys
        )

    def _ensure_started(self) -> None:
        if self.started_at is None:
            self.started_at = time.perf_counter()

    def _undo_correct_key(self) -> None:
        self.correct_keys = max(0, self.correct_keys - 1)
        self.total_keys = max(0, self.total_keys - 1)

    def _previous_required_index(self) -> int | None:
        index = self.index - 1
        while index >= 0:
            unit = self.passage.units[index]
            if unit.kind == "punct" and not self.check_punctuation:
                index -= 1
                continue
            return index
        return None

    def _skip_punctuation(self) -> None:
        if not self.check_punctuation:
            while (
                self.index < len(self.passage.units)
                and self.passage.units[self.index].kind == "punct"
            ):
                self.index += 1
        if self.index >= len(self.passage.units):
            self._finish()

    def _finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.finished_at = time.perf_counter()
        self.typed = ""
        self.error = False
        self.wrong = ""
