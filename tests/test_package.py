from zipfile import ZipFile

from scripts.package import RELEASE_FILES, build_archive


def test_archive_contains_only_release_sources(tmp_path):
    archive_path = build_archive(tmp_path / "release.zip")
    with ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == set(RELEASE_FILES)
        assert archive.testzip() is None
        assert "Flask" in archive.read("requirements.txt").decode("utf-8")
        assert not any(
            name.endswith((".db", ".sqlite3", ".pyc", ".env")) or ".venv" in name
            for name in archive.namelist()
        )
