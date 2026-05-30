from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Preset:
    name: str
    album_ids: list[str]
    person_filters: list[dict[str, Any]]
    start_date: str | None
    end_date: str | None
    media_type: str


def _read_json(url: str, token: str | None = None, timeout: float = 30) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _get_preset(base_url: str, preset_name: str, token: str | None = None, timeout: float = 30) -> Preset:
    payload = _read_json(f"{base_url}/api/presets/filters", token=token, timeout=timeout)
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected preset response shape")

    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("name") != preset_name:
            continue
        return Preset(
            name=preset_name,
            album_ids=[album_id for album_id in item.get("album_ids", []) if isinstance(album_id, str)],
            person_filters=[pf for pf in item.get("person_filters", []) if isinstance(pf, dict)],
            start_date=item.get("start_date") if isinstance(item.get("start_date"), str) else None,
            end_date=item.get("end_date") if isinstance(item.get("end_date"), str) else None,
            media_type=item.get("media_type") if isinstance(item.get("media_type"), str) else "photo",
        )

    raise RuntimeError(f"Preset '{preset_name}' not found")


def _build_query(preset: Preset) -> str:
    params: list[tuple[str, str]] = [("media_type", preset.media_type)]
    params.extend(("album_ids", album_id) for album_id in preset.album_ids)
    for person_filter in preset.person_filters:
        person_id = person_filter.get("personId")
        if isinstance(person_id, str) and person_id:
            params.append(("person_ids", person_id))
            mode = person_filter.get("mode") if isinstance(person_filter.get("mode"), str) else "optional"
            params.append(("person_modes", mode))
    if preset.start_date:
        params.append(("start_date", preset.start_date))
    if preset.end_date:
        params.append(("end_date", preset.end_date))
    return urlencode(params, doseq=True)


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value)
    return text.replace("|", "\\|")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure repeated dailyFX asset requests for a filter preset.")
    parser.add_argument("--base-url", default=os.environ.get("DAILYFX_BASE_URL", "http://127.0.0.1:8438"))
    parser.add_argument("--preset", default=os.environ.get("DAILYFX_PRESET", "TestA"))
    parser.add_argument("--count", type=int, default=int(os.environ.get("DAILYFX_COUNT", "50")))
    parser.add_argument("--token", default=os.environ.get("DAILYFX_TOKEN") or os.environ.get("APP_ACCESS_TOKEN"))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("DAILYFX_TIMEOUT", "30")))
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token
    preset = _get_preset(base_url, args.preset, token=token, timeout=args.timeout)
    query = _build_query(preset)

    durations: list[float] = []

    print("| # | ms | nazwa | data | osoby |")
    print("|---:|---:|---|---|---|")

    for index in range(1, args.count + 1):
        url = f"{base_url}/api/immich/assets?{query}"
        started = time.perf_counter()
        payload = _read_json(url, token=token, timeout=args.timeout)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        durations.append(elapsed_ms)

        items = payload.get("items") if isinstance(payload, dict) else None
        if not items:
            print(f"| {index} | {elapsed_ms:.1f} | - | - | brak wyników |")
            continue

        item = items[0]
        if not isinstance(item, dict):
            print(f"| {index} | {elapsed_ms:.1f} | - | - | nieprawidłowy wynik |")
            continue

        name = item.get("original_file_name") or item.get("id") or "-"
        date = item.get("created_at") or item.get("updated_at") or "-"
        people = ", ".join(
            p.get("name") or p.get("id") or ""
            for p in (item.get("people") or [])
            if isinstance(p, dict) and (p.get("name") or p.get("id"))
        ) or "-"
        print(f"| {index} | {elapsed_ms:.1f} | {_fmt(name)} | {_fmt(date)} | {_fmt(people)} |")

    if durations:
        print()
        print(f"Preset: `{preset.name}`")
        print(f"Requests: `{len(durations)}`")
        print(f"Mean: `{statistics.mean(durations):.1f} ms`")
        print(f"Min: `{min(durations):.1f} ms`")
        print(f"Max: `{max(durations):.1f} ms`")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
