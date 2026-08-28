#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from climb_evidence import load_json_object, source_revision, state_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    config_path = args.config or (state_dir(root) / "config.yaml")
    print(source_revision(load_json_object(config_path), root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
