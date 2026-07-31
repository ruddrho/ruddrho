#!/usr/bin/env python3
"""Render an animated Tokyo Night contribution calendar from JSON."""

from __future__ import annotations

import calendar
import html
import json
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "contributions.json"
OUTPUT = ROOT / "assets" / "contribution-heatmap.svg"

WIDTH = 1000
HEIGHT = 270
CELL = 11
GAP = 3
STEP = CELL + GAP
GRID_X = 152
GRID_Y = 70
PALETTE = ["#1a1b27", "#0e4429", "#006d32", "#26a641", "#39d353"]
TEXT = "#c0caf5"
DIM = "#565f89"
BLUE = "#7aa2f7"
GREEN = "#9ece6a"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def display_stat(value: object, suffix: str = "") -> str:
    if value is None:
        return "public data"
    return f"{int(value):,}{suffix}"


def month_labels(start: date, end: date) -> list[tuple[int, str]]:
    labels: list[tuple[int, str]] = []
    cursor = date(start.year, start.month, 1)
    if cursor < start:
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

    while cursor <= end:
        week = max(0, (cursor - start).days // 7)
        if week <= 52:
            labels.append((week, calendar.month_abbr[cursor.month]))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return labels


def main() -> int:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    username = str(payload.get("username", "ruddhro"))
    days = {str(item["date"]): item for item in payload.get("days", [])}
    stats = payload.get("stats", {})

    latest = max((date.fromisoformat(key) for key in days), default=date.today())
    end = latest
    start = end - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{esc(username)} GitHub contribution calendar</title>",
        "<desc id=\"desc\">Animated 53-week public contribution calendar refreshed daily.</desc>",
        "<style>",
        'text { font-family: "Fira Code", "JetBrains Mono", Consolas, monospace; }',
        ".day { opacity: 1; animation: reveal .38s ease-out both; }",
        "@keyframes reveal { from { opacity: 0; transform: translateY(7px); } "
        "to { opacity: 1; transform: translateY(0); } }",
        "</style>",
        '<rect x="1" y="1" width="998" height="268" rx="14" '
        'fill="#16161e" stroke="#292e42" stroke-width="2"/>',
        f'<text x="32" y="38" fill="{GREEN}" font-size="17">'
        f"$ {esc(username)}@github ~ ./contributions.sh</text>",
        f'<text x="968" y="38" text-anchor="end" fill="{DIM}" font-size="12">'
        "AUTO-REFRESH: DAILY</text>",
    ]

    for week, label in month_labels(start, end):
        x = GRID_X + week * STEP
        svg.append(f'<text x="{x}" y="59" fill="{DIM}" font-size="11">{label}</text>')

    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = GRID_Y + row * STEP + 10
        svg.append(
            f'<text x="{GRID_X - 14}" y="{y}" text-anchor="end" '
            f'fill="{DIM}" font-size="10">{label}</text>'
        )

    cursor = start
    while cursor <= end:
        week = (cursor - start).days // 7
        row = (cursor.weekday() + 1) % 7
        x = GRID_X + week * STEP
        y = GRID_Y + row * STEP
        item = days.get(cursor.isoformat(), {})
        try:
            level = max(0, min(int(item.get("level", 0)), 4))
        except (TypeError, ValueError):
            level = 0
        count = item.get("count")
        label = (
            f"{count} contributions on {cursor.isoformat()}"
            if count is not None
            else f"Contribution level {level} on {cursor.isoformat()}"
        )
        delay = min(2.6, 0.02 * (week + row))
        svg.append(
            f'<rect class="day" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="3" fill="{PALETTE[level]}" style="animation-delay:{delay:.2f}s">'
            f"<title>{esc(label)}</title></rect>"
        )
        cursor += timedelta(days=1)

    footer_y = 225
    total = display_stat(stats.get("total"))
    active = display_stat(stats.get("active_days"))
    current = display_stat(stats.get("current_streak"), " days")
    longest = display_stat(stats.get("longest_streak"), " days")

    stats_text = [
        ("CONTRIBUTIONS", total, BLUE),
        ("ACTIVE DAYS", active, GREEN),
        ("CURRENT STREAK", current, "#e0af68"),
        ("LONGEST STREAK", longest, "#bb9af7"),
    ]
    positions = [152, 365, 575, 790]
    for x, (label, value, color) in zip(positions, stats_text):
        svg.extend(
            [
                f'<text x="{x}" y="{footer_y}" fill="{DIM}" font-size="10">{label}</text>',
                f'<text x="{x}" y="{footer_y + 22}" fill="{color}" '
                f'font-size="16" font-weight="700">{esc(value)}</text>',
            ]
        )

    svg.append("</svg>")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
