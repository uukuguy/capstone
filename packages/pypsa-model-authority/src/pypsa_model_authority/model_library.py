"""Pinned, operator-installed PyPSA example Network assets."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import argparse
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from urllib.request import urlopen


class ModelLibraryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OfficialModel:
    catalog_id: str
    display_name: str
    upstream_function: str
    source_url: str
    size_bytes: int
    sha256: str
    business_theme: str


def _manifest() -> dict[str, object]:
    resource = files("pypsa_model_authority").joinpath("resources", "model-library.json")
    document = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "capstone-pypsa-model-library/1.0":
        raise ModelLibraryError("model library manifest is invalid")
    if document.get("pypsa_version") != "1.3.0":
        raise ModelLibraryError("model library PyPSA version is invalid")
    return document


def list_official_examples() -> tuple[OfficialModel, ...]:
    raw = _manifest().get("official_examples")
    if not isinstance(raw, list):
        raise ModelLibraryError("model library entries are invalid")
    try:
        entries = tuple(OfficialModel(**item) for item in raw)
    except (TypeError, ValueError) as exc:
        raise ModelLibraryError("model library entries are invalid") from exc
    names = [entry.catalog_id for entry in entries]
    if len(names) != len(set(names)) or any(
        entry.catalog_id != f"pypsa-example/{entry.upstream_function}"
        or not entry.upstream_function.replace("_", "").isalnum()
        or not entry.source_url == (
            f"https://data.pypsa.org/networks/examples/v1.3.0/{entry.upstream_function}.nc"
        )
        or entry.size_bytes <= 0
        or len(entry.sha256) != 64
        or any(char not in "0123456789abcdef" for char in entry.sha256)
        for entry in entries
    ):
        raise ModelLibraryError("model library entries are invalid")
    return entries


def get_official_example(catalog_id: str) -> OfficialModel:
    for entry in list_official_examples():
        if entry.catalog_id == catalog_id:
            return entry
    raise ModelLibraryError("official PyPSA model is not registered")


def default_root() -> Path:
    configured = os.environ.get("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR")
    if configured:
        return Path(configured)
    return Path.cwd() / ".grid-agent" / "runtime" / "pypsa-models"


def asset_path(entry: OfficialModel, *, root: Path | None = None) -> Path:
    return (root or default_root()) / f"{entry.upstream_function}.nc"


def verified_asset_path(catalog_id: str, *, root: Path | None = None) -> Path:
    entry = get_official_example(catalog_id)
    path = asset_path(entry, root=root)
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ModelLibraryError("official PyPSA model asset path is unsafe")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            digest = hashlib.sha256()
            size = 0
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                while chunk := stream.read(1_048_576):
                    size += len(chunk)
                    if size > entry.size_bytes:
                        raise ModelLibraryError("official PyPSA model asset size differs")
                    digest.update(chunk)
        finally:
            os.close(descriptor)
    except FileNotFoundError as exc:
        raise ModelLibraryError("official PyPSA model asset is not installed") from exc
    except OSError as exc:
        raise ModelLibraryError("official PyPSA model asset is unavailable") from exc
    if size != entry.size_bytes or digest.hexdigest() != entry.sha256:
        raise ModelLibraryError("official PyPSA model asset digest or size differs")
    return path


def install_official_example(catalog_id: str, *, root: Path | None = None) -> Path:
    entry = get_official_example(catalog_id)
    library_root = root or default_root()
    target = asset_path(entry, root=library_root)
    if library_root.is_symlink() or target.is_symlink():
        raise ModelLibraryError("official PyPSA model asset path is unsafe")
    library_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists():
        return verified_asset_path(catalog_id, root=library_root)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".download-", suffix=".nc", dir=library_root)
    temporary = Path(temporary_name)
    try:
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(descriptor, "wb") as output, urlopen(entry.source_url) as response:
            while chunk := response.read(1_048_576):
                size += len(chunk)
                if size > entry.size_bytes:
                    raise ModelLibraryError("official PyPSA model download size differs")
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if size != entry.size_bytes or digest.hexdigest() != entry.sha256:
            raise ModelLibraryError("official PyPSA model download digest or size differs")
        try:
            os.link(temporary, target)
        except FileExistsError:
            return verified_asset_path(catalog_id, root=library_root)
        return verified_asset_path(catalog_id, root=library_root)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pypsa_model_authority.model_library")
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("list")
    installer = command.add_parser("install")
    installer.add_argument("catalog_ids", nargs="*")
    installer.add_argument("--all", action="store_true")
    options = parser.parse_args(argv)
    if options.command == "list":
        from pypsa_model_authority.catalog import list_registered_models
        print(json.dumps({"schema": "capstone-pypsa-model-catalog/1.0", "models": list_registered_models()}, ensure_ascii=False))
        return 0
    if options.all == bool(options.catalog_ids):
        parser.error("choose --all or one or more catalog IDs")
    chosen = (
        tuple(entry.catalog_id for entry in list_official_examples())
        if options.all else tuple(options.catalog_ids)
    )
    try:
        installed = [install_official_example(catalog_id) for catalog_id in chosen]
    except ModelLibraryError as exc:
        parser.exit(1, f"model library installation failed: {exc}\n")
    print(json.dumps({"installed": [path.stem for path in installed]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
