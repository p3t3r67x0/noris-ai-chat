"""Check built archives without extracting or exposing local/operator data."""

import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def check_package(path: Path) -> None:
    source = path.name.endswith(".tar.gz")
    if source:
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            if any(not (member.isfile() or member.isdir()) for member in members):
                raise ValueError("Source package contains links or special files")
            names = [member.name for member in members]
    elif path.suffix == ".whl":
        with ZipFile(path) as archive:
            if any(stat.S_ISLNK(member.external_attr >> 16) for member in archive.infolist()):
                raise ValueError("Wheel contains links")
            names = archive.namelist()
    else:
        raise ValueError("Unsupported backend package")
    expected = path.name.removesuffix(".tar.gz")
    metadata = "-".join(path.name.split("-")[:2]) + ".dist-info"
    for name in names:
        parts = PurePosixPath(name).parts
        if not parts or name.startswith("/") or ".." in parts or "\\" in name:
            raise ValueError("Invalid backend package path")
        # Hatch adds a root .gitignore to preserve the selected inputs on rebuild.
        if source and parts == (expected, ".gitignore"):
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            raise ValueError("Backend package contains local artifacts")
        if source:
            if parts[0] != expected:
                raise ValueError("Invalid source package root")
            if len(parts) > 1 and parts[1] not in {
                "src",
                "migrations",
                "scripts",
                "tests",
                "alembic.ini",
                "pyproject.toml",
                "uv.lock",
                "PKG-INFO",
            }:
                raise ValueError("Source package contains unexpected inputs")
        elif parts[0] not in {"noris_ai", metadata}:
            raise ValueError("Wheel contains unexpected inputs")
    if not any(name.endswith("noris_ai/main.py") for name in names):
        raise ValueError("Backend package is missing application source")
    if source and not any("/migrations/versions/" in name for name in names):
        raise ValueError("Source package is missing migrations")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        check_package(Path(argument))
    print("Backend packages contain only approved source inputs.")
