from __future__ import annotations

from youtube2datasets.models import TimeRange


def parse_timecode(value: str | float | int) -> float:
    if isinstance(value, (float, int)):
        if value < 0:
            raise ValueError("Time values must be non-negative.")
        return float(value)

    text = value.strip()
    if not text:
        raise ValueError("Time value cannot be empty.")

    if text.replace(".", "", 1).isdigit():
        return parse_timecode(float(text))

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid timecode: {value}")

    multipliers = [1, 60, 3600]
    total = 0.0
    for index, part in enumerate(reversed(parts)):
        try:
            total += float(part) * multipliers[index]
        except ValueError as exc:
            raise ValueError(f"Invalid timecode: {value}") from exc
    return total


def format_timecode(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def parse_time_range(raw_range: str) -> TimeRange:
    if "-" not in raw_range:
        raise ValueError(f"Invalid range '{raw_range}'. Expected START-END.")

    start_text, end_text = raw_range.split("-", 1)
    start = parse_timecode(start_text)
    end = parse_timecode(end_text)
    if end <= start:
        raise ValueError(f"Invalid range '{raw_range}'. End must be greater than start.")
    return TimeRange(start=start, end=end)


def is_in_ranges(timestamp: float, ranges: list[TimeRange]) -> bool:
    return any(item.start <= timestamp < item.end for item in ranges)
