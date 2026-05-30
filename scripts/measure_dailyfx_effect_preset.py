#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter

sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.effect_preset import EffectPresetModel
except ImportError:
    print("Error: Could not import backend database models. Run from virtualenv or project root.")
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate repeated random selection of effects in a preset.")
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL", "sqlite:///../data/app.db"))
    parser.add_argument("--preset", default="AI", help="Name of the effect preset to load.")
    parser.add_argument("--count", type=int, default=100, help="Number of random choices to perform.")
    args = parser.parse_args()

    db_path = args.db_url
    if db_path.startswith("sqlite:///../"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = f"sqlite:///{os.path.join(base_dir, 'data', 'app.db')}"

    engine = create_engine(db_path)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        preset = session.query(EffectPresetModel).filter_by(name=args.preset).first()
        if not preset:
            print(f"Error: Effect preset '{args.preset}' not found in database.")
            presets = session.query(EffectPresetModel).all()
            print("Available presets:")
            for p in presets:
                print(f"  * {p.name}")
            return 1

        config_dict = json.loads(preset.groups_json) if isinstance(preset.groups_json, str) else preset.groups_json
        active_groups = [(name, data) for name, data in config_dict.items() if data.get("enabled", False)]

        if not active_groups:
            print(f"Error: Effect preset '{args.preset}' has no enabled effects.")
            return 1

        print(f"Preset: `{preset.name}`")
        print(f"Active effects count: `{len(active_groups)}`")
        print(f"Requested simulations: `{args.count}`")
        print()
        print("| # | Effect Name | Weight |")
        print("|---:|---|---|")
        for idx, (name, data) in enumerate(active_groups, 1):
            print(f"| {idx} | `{name}` | `{data.get('weight', 1)}` |")
        print()

        weights = [data.get("weight", 1) for _, data in active_groups]
        selections = []
        for _ in range(args.count):
            selected_name, _ = random.choices(active_groups, weights=weights, k=1)[0]
            selections.append(selected_name)

        counts = Counter(selections)

        print("| Position | Effect Module | Count | Percentage |")
        print("|:---:|:---|:---:|:---:|")
        for idx, (name, count) in enumerate(counts.most_common(), 1):
            pct = (count / args.count) * 100.0
            print(f"| {idx} | `{name}` | **{count}** | {pct:.1f}% |")
        print(f"| | **TOTAL** | **{args.count}** | **100%** |")

    finally:
        session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
