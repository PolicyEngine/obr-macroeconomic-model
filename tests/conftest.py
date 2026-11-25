"""Shared pytest configuration.

Tests marked `slow` (the full-solver suites, which build and solve the
372-equation model many times) are skipped by default so a plain `pytest`
run finishes in about 20 seconds. Run them with `pytest --runslow`.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="also run slow full-solver tests",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow full-solver test; use --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
