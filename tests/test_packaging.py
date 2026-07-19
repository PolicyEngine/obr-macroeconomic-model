"""Packaging integrity: the shipped data assets must survive installation.

The model is useless without its data assets — the OBR model source, the
variable dictionary, the four EFO workbooks and the seed snapshots. Those are
not Python modules; they ship only because ``[tool.setuptools.package-data]``
lists globs that happen to match them. A file added under a new extension or a
new subdirectory is picked up fine by an editable/in-tree run (CI's ``uv sync``
installs the project in place) and is missing only from a built wheel — so the
existing suites, which all read from the source tree, cannot catch it. The
break surfaces at import time for whoever installs the package.

These tests are hermetic (no network, no solver build) and close that gap by
checking every shipped asset against the declared globs, plus the loader paths
that resolve them.
"""

import fnmatch
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - py310 fallback
    tomllib = pytest.importorskip("tomli")

import obr_macro
from obr_macro.data import DATA_DIR

PACKAGE_ROOT = Path(obr_macro.__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent

# Asset directories whose contents must all be covered by package-data globs.
ASSET_DIRS = ("_data", "seeds")

# Files that must exist by name — the loaders reference these directly, so a
# rename must break here rather than at a user's import.
REQUIRED_ASSETS = [
    "_data/obr_model_code_october_2025.txt",
    "_data/obr_model_variables_october_2025.xlsx",
    "_data/obr_efo_november_2025_aggregates.xlsx",
    "_data/obr_efo_november_2025_economy.xlsx",
    "_data/obr_efo_november_2025_expenditure.xlsx",
    "_data/obr_efo_november_2025_receipts.xlsx",
    "seeds/model_glossary.json",
    "seeds/snapshot_manifest.json",
    "seeds/ons_exogenous_snapshot.csv",
]


def _pyproject():
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def _package_data_globs():
    cfg = _pyproject()["tool"]["setuptools"]["package-data"]
    return cfg["obr_macro"]


def _shipped_asset_files():
    """Every non-generated file under the asset directories."""
    out = []
    for sub in ASSET_DIRS:
        for path in sorted((PACKAGE_ROOT / sub).rglob("*")):
            if path.is_dir() or path.name.startswith("."):
                continue
            if "__pycache__" in path.parts:
                continue
            out.append(path.relative_to(PACKAGE_ROOT).as_posix())
    return out


def test_asset_directories_are_not_empty():
    """Guard against the whole check passing vacuously on a stripped checkout."""
    assets = _shipped_asset_files()
    assert len(assets) >= len(REQUIRED_ASSETS), f"asset dirs look empty: {assets}"


@pytest.mark.parametrize("relpath", REQUIRED_ASSETS)
def test_required_asset_exists(relpath):
    assert (PACKAGE_ROOT / relpath).is_file(), f"missing shipped asset {relpath}"


def test_every_shipped_asset_matches_a_package_data_glob():
    """The real gap: an asset present in-tree but not matched by any declared
    glob is silently dropped from a built wheel."""
    globs = _package_data_globs()
    uncovered = [
        rel
        for rel in _shipped_asset_files()
        if not any(fnmatch.fnmatch(rel, g) for g in globs)
    ]
    assert not uncovered, (
        "these files ship in-tree but no package-data glob matches them, so a "
        f"built wheel omits them: {uncovered} (declared globs: {globs})"
    )


def test_package_data_globs_all_match_something():
    """A glob matching nothing is a stale declaration — usually the residue of
    a renamed asset, and a hint the real file is now uncovered."""
    assets = _shipped_asset_files()
    for g in _package_data_globs():
        assert any(fnmatch.fnmatch(rel, g) for rel in assets), (
            f"package-data glob {g!r} matches no shipped file"
        )


def test_data_dir_resolves_inside_the_installed_package():
    """DATA_DIR must be package-relative, not a path into a developer's
    checkout or a download cache — that is what makes the wheel self-contained."""
    assert DATA_DIR.is_dir()
    assert DATA_DIR.resolve().is_relative_to(PACKAGE_ROOT.resolve())
    assert (DATA_DIR / "obr_model_code_october_2025.txt").is_file()


def test_model_source_is_substantive():
    """The shipped OBR model source must be the real file, not a placeholder or
    an LFS pointer stub."""
    src = (DATA_DIR / "obr_model_code_october_2025.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    # The OBR model is ~372 equations; count assignment lines rather than bytes.
    equation_lines = [
        ln for ln in src.splitlines() if "=" in ln and not ln.startswith("'")
    ]
    assert len(equation_lines) > 300, (
        f"model source has only {len(equation_lines)} equation lines — "
        "looks like a placeholder or a truncated download"
    )


def test_workbooks_are_real_xlsx_files():
    """Each EFO workbook must be a genuine zip-format xlsx (an LFS pointer or a
    truncated download would still satisfy an existence check)."""
    for rel in REQUIRED_ASSETS:
        if not rel.endswith(".xlsx"):
            continue
        path = PACKAGE_ROOT / rel
        assert path.stat().st_size > 10_000, f"{rel} suspiciously small"
        with open(path, "rb") as fh:
            assert fh.read(2) == b"PK", f"{rel} is not a valid xlsx (zip) file"


def test_declared_dependencies_cover_the_import_surface():
    """The workbook loaders need openpyxl and the solver needs scipy; both are
    easy to lose from `dependencies` while still passing locally."""
    deps = " ".join(_pyproject()["project"]["dependencies"]).lower()
    for pkg in ("numpy", "pandas", "openpyxl", "scipy"):
        assert pkg in deps, f"{pkg} missing from project dependencies"
