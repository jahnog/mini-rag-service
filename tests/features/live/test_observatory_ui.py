from pytest_bdd import scenarios

from tests.features.live import ui_steps as _ui_steps  # noqa: F401

scenarios("observatory_ui.feature")
