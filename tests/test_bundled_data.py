"""The wheel's copies of the spec files (src/sf_smartfabric/data/) must match the normative copies
at the repository root, and every bundled file must be readable through the package."""
from pathlib import Path

import pytest

from sf_smartfabric import _bundled

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "sf_smartfabric" / "data"
SOURCES = sorted(
    [p for p in (ROOT / "schema").glob("*.json")]
    + [ROOT / "examples" / "fleet.example.json"]
    + [p for p in (ROOT / "spec" / "vectors").glob("*.json")]
)


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_bundled_copy_matches_source(src):
    rel = src.relative_to(ROOT)
    copy = DATA / rel
    assert copy.is_file(), f"{rel} is not bundled: copy it to src/sf_smartfabric/data/{rel}"
    assert copy.read_bytes() == src.read_bytes(), f"src/sf_smartfabric/data/{rel} differs from {rel}"


def test_no_stray_bundled_files():
    bundled = {p.relative_to(DATA) for p in DATA.rglob("*.json")}
    assert bundled == {p.relative_to(ROOT) for p in SOURCES}


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_read_text_finds_every_file(src):
    assert _bundled.read_text(*src.relative_to(ROOT).parts) == src.read_text(encoding="utf-8")
