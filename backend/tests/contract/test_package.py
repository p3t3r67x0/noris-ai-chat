import io
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.check_package import check_package


def package(tmp_path: Path, extra: str | None = None) -> Path:
    path = tmp_path / "noris_ai_backend-0.1.0.tar.gz"
    names = ["src/noris_ai/main.py", "migrations/versions/initial.py"]
    if extra:
        names.append(extra)
    with tarfile.open(path, "w:gz") as archive:
        for name in names:
            entry = tarfile.TarInfo(f"noris_ai_backend-0.1.0/{name}")
            entry.size = 1
            archive.addfile(entry, io.BytesIO(b"x"))
    return path


def test_application_and_migrations_remain_in_source_distribution(tmp_path: Path):
    check_package(package(tmp_path))
    check_package(package(tmp_path, ".gitignore"))


@pytest.mark.parametrize(
    "local",
    [
        ".local/attachments/private",
        ".env",
        "tests/.local/provider.json",
        "../outside",
        "operator/credentials",
        "src/__pycache__/module.pyc",
    ],
)
def test_source_distribution_rejects_local_uploads_configuration_and_traversal(
    tmp_path: Path, local: str
):
    with pytest.raises(ValueError):
        check_package(package(tmp_path, local))


def test_source_distribution_rejects_links_without_extraction(tmp_path: Path):
    path = package(tmp_path)
    with tarfile.open(path, "w:gz") as archive:
        entry = tarfile.TarInfo("noris_ai_backend-0.1.0/src/noris_ai/main.py")
        entry.type = tarfile.SYMTYPE
        entry.linkname = "/private/provider-config"
        archive.addfile(entry)
    with pytest.raises(ValueError, match="links"):
        check_package(path)


@pytest.mark.parametrize(
    "local", [None, "noris_ai/.env", "noris_ai/../../private", "/private", "operator/credentials"]
)
def test_wheel_contains_only_application_and_metadata(tmp_path: Path, local: str | None):
    path = tmp_path / "noris_ai_backend-0.1.0-py3-none-any.whl"
    with ZipFile(path, "w") as archive:
        archive.writestr("noris_ai/main.py", "")
        archive.writestr("noris_ai_backend-0.1.0.dist-info/METADATA", "")
        if local:
            archive.writestr(local, "")
    if local:
        with pytest.raises(ValueError):
            check_package(path)
    else:
        check_package(path)
