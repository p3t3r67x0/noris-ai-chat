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
            file_names = [member.name for member in members if member.isfile()]
    elif path.suffix == ".whl":
        with ZipFile(path) as archive:
            if any(stat.S_ISLNK(member.external_attr >> 16) for member in archive.infolist()):
                raise ValueError("Wheel contains links")
            names = archive.namelist()
            file_names = [member.filename for member in archive.infolist() if not member.is_dir()]
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
            if len(parts) > 2 and parts[1] == "src" and parts[2] != "noris_ai":
                raise ValueError("Source package contains an unexpected module")
        elif parts[0] not in {"noris_ai", metadata}:
            raise ValueError("Wheel contains unexpected inputs")
    files = (
        {name.removeprefix(expected + "/") for name in file_names} if source else set(file_names)
    )
    if ("src/noris_ai/main.py" if source else "noris_ai/main.py") not in files:
        raise ValueError("Backend package is missing application source")
    if source:
        if not {"pyproject.toml", "uv.lock", "alembic.ini"}.issubset(files):
            raise ValueError("Source package is missing build configuration")
        for directory in ("migrations/versions/", "scripts/", "tests/"):
            if not any(name.startswith(directory) and name.endswith(".py") for name in files):
                raise ValueError("Source package is missing required inputs")
    elif not {f"{metadata}/{name}" for name in ("METADATA", "WHEEL", "RECORD")}.issubset(files):
        raise ValueError("Wheel is missing build metadata")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        check_package(Path(argument))
    print("Backend packages contain only approved source inputs.")
