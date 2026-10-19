"""Собрать чистый ZIP по явному списку исходных файлов, без БД и секретов."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILES = (
    "app.py",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    ".gitignore",
    ".gitattributes",
    "README.md",
    "EVIDENCE.md",
    ".github/workflows/ci.yml",
    "templates/index.html",
    "static/style.css",
    "scripts/package.py",
    "scripts/deploy_test.py",
    "scripts/healthcheck.py",
    "tests/conftest.py",
    "tests/test_app.py",
    "tests/test_package.py",
)


def build_archive(output):
    for name in RELEASE_FILES:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Required regular source file missing: {name}")
    output = Path(output).resolve()
    sources = {(ROOT / name).resolve() for name in RELEASE_FILES}
    if output in sources:
        raise ValueError("Archive must not overwrite a source file")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name in RELEASE_FILES:
            archive.write(ROOT / name, arcname=name)
    print(f"Package created: {output} ({output.stat().st_size} bytes)")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "devops-task-manager.zip")
    build_archive(parser.parse_args().output)
