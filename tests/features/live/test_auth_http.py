from pytest_bdd import scenarios

from tests.features.live import http_steps as _http_steps  # noqa: F401

scenarios("auth_http.feature")
