from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run live BCRA integration tests",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="live BCRA; pass --run-integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
