#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_closure import execute_release_closure


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    score = execute_release_closure(args.root, args.run_dir)
    print(json.dumps(score, ensure_ascii=False, sort_keys=True))
    return 0 if score["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
