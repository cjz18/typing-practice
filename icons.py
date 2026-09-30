"""Rasterize the bundled Phosphor icons into Tk photos."""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import tkinter as tk

_TOKEN = re.compile(r"[MmLlHhVvCcSsQqAaZz]|[-+]?(?:\d*\.\d+|\d+)")


def icon_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icons"
    return Path(__file__).resolve().parent / "assets" / "icons"


class IconSet:
    def __init__(self) -> None:
        self._paths: dict[str, str] = {}
        self._cache: dict[tuple[str, int, str], tk.PhotoImage] = {}

    def photo(self, master: tk.Misc, name: str, size: int, color: str) -> tk.PhotoImage | None:
        key = (name, size, color.lower())
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        path = self._path(name)
        if not path:
            return None
        image = _rasterize(path, size, color)
        self._cache[key] = image
        # Keep the photo alive for as long as the widget that owns the master exists.
        master = master.winfo_toplevel()
        holder = getattr(master, "_icon_photos", None)
        if holder is None:
            holder = []
            master._icon_photos = holder
        holder.append(image)
        return image

    def _path(self, name: str) -> str:
        if name in self._paths:
            return self._paths[name]
        file = icon_dir() / f"{name}-light.svg"
        try:
            text = file.read_text(encoding="utf-8")
        except OSError:
            self._paths[name] = ""
            return ""
        match = re.search(r'<path d="([^"]+)"', text)
        data = match.group(1) if match else ""
        self._paths[name] = data
        return data


def _rasterize(path_data: str, size: int, color: str) -> tk.PhotoImage:
    samples = size * 4
    scale = samples / 256
    mask = [[0] * samples for _ in range(samples)]
    for line in _polylines(path_data):
        points = [(x * scale, y * scale) for x, y in line]
        _fill(mask, points, samples)
    image = tk.PhotoImage(width=size, height=size)
    threshold = 8
    for y in range(size):
        for x in range(size):
            covered = 0
            oy = y * 4
            ox = x * 4
            for sy in range(4):
                band = mask[oy + sy]
                covered += band[ox] + band[ox + 1] + band[ox + 2] + band[ox + 3]
            if covered >= threshold:
                image.put(color, to=(x, y))
    return image


def _polylines(path_data: str) -> list[list[tuple[float, float]]]:
    tokens = _TOKEN.findall(path_data)
    index = 0
    command = ""
    x = y = 0.0
    start = (0.0, 0.0)
    control = (0.0, 0.0)
    previous = ""
    current: list[tuple[float, float]] = []
    lines: list[list[tuple[float, float]]] = []

    def number() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    def pair(relative: bool) -> tuple[float, float]:
        px, py = number(), number()
        if relative:
            px += x
            py += y
        return px, py

    def close() -> None:
        nonlocal current
        if len(current) >= 2:
            if current[0] != current[-1]:
                current.append(current[0])
            lines.append(current)
        current = []

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in ("Z", "z"):
                close()
                x, y = start
                previous = "Z"
            continue
        relative = command.islower()
        kind = command.upper()
        if kind == "M":
            if current:
                close()
            x, y = pair(relative)
            start = (x, y)
            current = [(x, y)]
            command = "l" if relative else "L"
            previous = "M"
        elif kind == "L":
            x, y = pair(relative)
            current.append((x, y))
            previous = "L"
        elif kind == "H":
            nx = number()
            x = x + nx if relative else nx
            current.append((x, y))
            previous = "H"
        elif kind == "V":
            ny = number()
            y = y + ny if relative else ny
            current.append((x, y))
            previous = "V"
        elif kind == "C":
            c1 = pair(relative)
            c2 = pair(relative)
            end = pair(relative)
            current.extend(_flatten_cubic((x, y), c1, c2, end))
            control = c2
            x, y = end
            previous = "C"
        elif kind == "S":
            if previous == "C":
                c1 = (2 * x - control[0], 2 * y - control[1])
            else:
                c1 = (x, y)
            c2 = pair(relative)
            end = pair(relative)
            current.extend(_flatten_cubic((x, y), c1, c2, end))
            control = c2
            x, y = end
            previous = "C"
        elif kind == "Q":
            c1 = pair(relative)
            end = pair(relative)
            current.extend(_flatten_quadratic((x, y), c1, end))
            x, y = end
            previous = "Q"
        elif kind == "A":
            rx, ry = abs(number()), abs(number())
            rotation = number()
            large = number() != 0
            sweep = number() != 0
            end = pair(relative)
            current.extend(_arc_points((x, y), rx, ry, rotation, large, sweep, end))
            x, y = end
            previous = "A"
        else:
            break
    if current:
        close()
    return lines


    return points


def _flatten_quadratic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> list[tuple[float, float]]:
    points = []
    steps = 6
    for step in range(1, steps + 1):
        t = step / steps
        u = 1 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        points.append((x, y))
    return points


def _arc_points(
    start: tuple[float, float],
    rx: float,
    ry: float,
    rotation: float,
    large: bool,
    sweep: bool,
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    x1, y1 = start
    x2, y2 = end
    if (x1, y1) == (x2, y2):
        return []
    if rx == 0 or ry == 0:
        return [end]
    phi = math.radians(rotation)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)
    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    radius_scale = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if radius_scale > 1:
        scale = math.sqrt(radius_scale)
        rx *= scale
        ry *= scale
    rx2 = rx * rx
    ry2 = ry * ry
    numerator = rx2 * ry2 - rx2 * y1p * y1p - ry2 * x1p * x1p
    denominator = rx2 * y1p * y1p + ry2 * x1p * x1p
    coef = math.sqrt(max(0.0, numerator / denominator)) if denominator else 0.0
    if large == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = coef * -ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        length = math.hypot(ux, uy) * math.hypot(vx, vy)
        value = math.acos(max(-1.0, min(1.0, dot / length))) if length else 0.0
        if ux * vy - uy * vx < 0:
            value = -value
        return value

    theta = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and delta > 0:
        delta -= math.tau
    elif sweep and delta < 0:
        delta += math.tau
    steps = max(6, int(abs(delta) / (math.pi / 8)))
    points = []
    for step in range(1, steps + 1):
        t = theta + delta * step / steps
        cos_t = math.cos(t)
        sin_t = math.sin(t)
        points.append(
            (
                cos_phi * rx * cos_t - sin_phi * ry * sin_t + cx,
                sin_phi * rx * cos_t + cos_phi * ry * sin_t + cy,
            )
        )
    return points


def _flatten_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> list[tuple[float, float]]:
    points = []
    steps = 8
    for step in range(1, steps + 1):
        t = step / steps
        u = 1 - t
        x = (u * u * u * p0[0]) + (3 * u * u * t * p1[0]) + (3 * u * t * t * p2[0]) + (t * t * t * p3[0])
        y = (u * u * u * p0[1]) + (3 * u * u * t * p1[1]) + (3 * u * t * t * p2[1]) + (t * t * t * p3[1])
        points.append((x, y))
    return points


def _fill(mask: list[list[int]], points: list[tuple[float, float]], samples: int) -> None:
    edges = list(zip(points, points[1:]))
    for y in range(samples):
        scan = y + 0.5
        hits: list[tuple[float, int]] = []
        for (x1, y1), (x2, y2) in edges:
            if y1 == y2:
                continue
            if y1 < y2:
                if not (y1 <= scan < y2):
                    continue
                direction = 1
            else:
                if not (y2 <= scan < y1):
                    continue
                direction = -1
            t = (scan - y1) / (y2 - y1)
            hits.append((x1 + t * (x2 - x1), direction))
        hits.sort(key=lambda item: item[0])
        winding = 0
        row = mask[y]
        cursor = 0.0
        for x, direction in hits:
            if winding != 0:
                start = max(0, int(cursor))
                end = min(samples, int(x))
                for px in range(start, end):
                    row[px] = 1
            winding += direction
            cursor = x
