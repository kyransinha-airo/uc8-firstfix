"""Generate deterministic CU-2 telemetry for the FirstFix mock pack.

Writes two files under data/mock-data/03_structured/:
  telemetry_readings_pre.csv   48 h before the 09:30 dispatch run (phase 1)
  telemetry_readings_post.csv  14:05-16:05 after the visit (phase 2)

No randomness: noise is a sum of sines, so every run gives byte-identical files.
Usage (from the repo root): python data/mock-data/build_telemetry.py
"""
import csv
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

TZ = "-06:00"


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + TZ


def in_window(dt, windows):
    return any(a <= dt <= b for a, b in windows)


def fan_value(i, dt, dips):
    base = 3.2 + 0.08 * math.sin(i / 37.0) + 0.04 * math.sin(i / 7.3)
    if in_window(dt, dips):
        return round(2.45 + 0.05 * math.sin(i / 3.0), 2)
    return round(base, 2)


def pressure_pre(i, dt):
    base = 272 + 9 * math.sin(i / 90.0) + 3 * math.sin(i / 11.0)
    ramp_start = datetime(2026, 12, 1, 6, 0)
    if dt >= ramp_start:
        minutes = (dt - ramp_start).total_seconds() / 60
        base += minutes * (84 / 190)  # climbs to ~356 psig by 09:10
    return round(base, 1)


def pressure_post(i):
    return round(284 + 6 * math.sin(i / 25.0) + 2 * math.sin(i / 6.0), 1)


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series_id", "ts", "value"])
        w.writerows(rows)


def main(root: Path):
    out = root / "03_structured"

    start = datetime(2026, 11, 29, 9, 30)
    end = datetime(2026, 12, 1, 9, 30)
    pre_dips = [
        (datetime(2026, 11, 29, 22, 14), datetime(2026, 11, 29, 22, 31)),
        (datetime(2026, 11, 30, 15, 40), datetime(2026, 11, 30, 15, 58)),
    ]
    rows, i, dt = [], 0, start
    while dt <= end:
        rows.append(["CU2-DP", ts(dt), pressure_pre(i, dt)])
        rows.append(["CU2-FC", ts(dt), fan_value(i, dt, pre_dips)])
        i += 1
        dt += timedelta(minutes=1)
    write(out / "telemetry_readings_pre.csv", rows)

    start = datetime(2026, 12, 1, 14, 5)
    end = datetime(2026, 12, 1, 16, 5)
    post_dips = [
        (datetime(2026, 12, 1, 14, 41), datetime(2026, 12, 1, 14, 47)),
        (datetime(2026, 12, 1, 15, 22), datetime(2026, 12, 1, 15, 29)),
    ]
    rows, i, dt = [], 0, start
    while dt <= end:
        rows.append(["CU2-DP", ts(dt), pressure_post(i)])
        rows.append(["CU2-FC", ts(dt), fan_value(i, dt, post_dips)])
        i += 1
        dt += timedelta(minutes=1)
    write(out / "telemetry_readings_post.csv", rows)


if __name__ == "__main__":
    main(Path(__file__).resolve().parent)
