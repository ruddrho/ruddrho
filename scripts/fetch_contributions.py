#!/usr/bin/env python3
"""Fetch a public GitHub contribution calendar without a personal access token."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "contributions.json"
DEFAULT_USERNAME = "ruddrho"


def parse_count(text: str) -> int | None:
    normalized = " ".join(text.split())
    if re.search(r"\bno contributions?\b", normalized, flags=re.IGNORECASE):
        return 0
    match = re.search(r"([\d,]+)\s+contributions?", normalized, flags=re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def parse_day(cell, soup: BeautifulSoup) -> dict[str, object] | None:
    raw_date = cell.get("data-date")
    if not raw_date:
        return None

    try:
        date.fromisoformat(raw_date)
    except ValueError:
        return None

    count: int | None = None
    raw_count = cell.get("data-count")
    if raw_count is not None:
        try:
            count = int(raw_count)
        except ValueError:
            count = None

    labels: list[str] = []
    for attribute in ("aria-label", "title"):
        value = cell.get(attribute)
        if value:
            labels.append(value)

    cell_id = cell.get("id")
    if cell_id:
        tooltip = soup.select_one(f'tool-tip[for="{cell_id}"]')
        if tooltip:
            labels.append(tooltip.get_text(" ", strip=True))

    if count is None:
        for label in labels:
            count = parse_count(label)
            if count is not None:
                break

    try:
        level = int(cell.get("data-level", 0))
    except (TypeError, ValueError):
        level = 0

    level = max(0, min(level, 4))
    return {"date": raw_date, "count": count, "level": level}


def compute_streaks(days: list[dict[str, object]]) -> tuple[int, int]:
    known = {
        date.fromisoformat(str(day["date"])): int(day["count"])
        for day in days
        if day.get("count") is not None
    }
    if not known:
        return 0, 0

    ordered = sorted(known)
    longest = 0
    running = 0
    previous = None

    for current in ordered:
        if known[current] > 0:
            if previous is not None and (current - previous).days == 1:
                running += 1
            else:
                running = 1
            longest = max(longest, running)
            previous = current
        else:
            running = 0
            previous = None

    latest = ordered[-1]
    current_streak = 0
    cursor = latest
    while cursor in known:
        if known[cursor] > 0:
            current_streak += 1
            cursor = cursor.fromordinal(cursor.toordinal() - 1)
        elif cursor == latest:
            cursor = cursor.fromordinal(cursor.toordinal() - 1)
        else:
            break

    return current_streak, longest


def main() -> int:
    username = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("GITHUB_USERNAME", DEFAULT_USERNAME)
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise SystemExit(f"Invalid GitHub username: {username!r}")

    url = f"https://github.com/users/{username}/contributions"
    response = requests.get(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "ruddhro-profile-readme/1.0",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    parsed: dict[str, dict[str, object]] = {}
    for cell in soup.select("[data-date]"):
        day = parse_day(cell, soup)
        if day:
            parsed[str(day["date"])] = day

    days = [parsed[key] for key in sorted(parsed)]
    if len(days) < 300:
        raise RuntimeError(
            f"Only {len(days)} contribution days were parsed. "
            "GitHub's public calendar markup may have changed."
        )

    known_counts = [int(day["count"]) for day in days if day.get("count") is not None]
    current_streak, longest_streak = compute_streaks(days)
    payload = {
        "username": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": url,
        "days": days,
        "stats": {
            "total": sum(known_counts) if known_counts else None,
            "active_days": sum(1 for count in known_counts if count > 0),
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "counts_available": bool(known_counts),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(days)} days for {username} to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
