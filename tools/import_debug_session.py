"""Import a Capstone session debug ZIP into a new private directory."""

import argparse
from pathlib import Path
from zipfile import BadZipFile

from capstone_agent.debug_session_handoff import import_handoff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--import-to", type=Path, required=True)
    parser.add_argument("--max-uncompressed-bytes", type=int, required=True)
    args = parser.parse_args()
    if args.max_uncompressed_bytes <= 0:
        parser.error("--max-uncompressed-bytes must be positive")
    try:
        destination = import_handoff(args.archive, args.import_to, max_uncompressed_bytes=args.max_uncompressed_bytes)
    except (BadZipFile, OSError, ValueError) as error:
        parser.exit(1, f"Import failed: {error}\n")
    print(destination)


if __name__ == "__main__":
    main()
