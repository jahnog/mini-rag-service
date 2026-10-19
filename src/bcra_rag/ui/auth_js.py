"""Browser JavaScript for the login widgets.

The scripts live in `ui/js/*.js`. They contain `__AUTH_NAME__` placeholders
that are replaced here with JSON-encoded copy from `ui/config.py`, so the
user-facing text is defined in one place.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bcra_rag.ui.config import (
    AUTH_STATUS_CODE_REJECTED,
    AUTH_STATUS_INVALID_EMAIL,
    AUTH_STATUS_INVALID_ORIGIN,
    AUTH_STATUS_SENDING,
    AUTH_STATUS_SIGNED_IN,
    AUTH_STATUS_SIGNED_OUT,
    AUTH_STATUS_SMTP_FAIL,
    AUTH_STATUS_SMTP_OK,
    AUTH_STATUS_SMTP_PROBLEM,
    AUTH_STATUS_TOO_MANY_ATTEMPTS,
    AUTH_STATUS_VERIFY_FAILED,
)

JS_DIRECTORY = Path(__file__).with_name("js")
AUTH_REQUEST_JS_PATH = JS_DIRECTORY / "auth_request.js"
AUTH_VERIFY_JS_PATH = JS_DIRECTORY / "auth_verify.js"
AUTH_LOGOUT_JS_PATH = JS_DIRECTORY / "auth_logout.js"

_PLACEHOLDER_PATTERN = re.compile(r"__AUTH_[A-Z_]+__")


def fill_placeholders(template: str, values: dict[str, str]) -> str:
    """Replace each `__AUTH_NAME__` token in the template with its JSON-encoded value.

    Raises ValueError when a value has no matching token or a token has no
    value, so a typo fails loudly instead of shipping a broken script.
    """
    unused_tokens = [token for token in values if token not in template]
    if unused_tokens:
        raise ValueError(f"placeholders not found in template: {sorted(unused_tokens)}")
    filled = template
    for token, value in values.items():
        filled = filled.replace(token, value)
    unfilled_tokens = sorted(set(_PLACEHOLDER_PATTERN.findall(filled)))
    if unfilled_tokens:
        raise ValueError(f"placeholders without a value: {unfilled_tokens}")
    return filled


def _as_js_literal(text: str) -> str:
    """Encode text as a JavaScript string literal, keeping accents readable."""
    return json.dumps(text, ensure_ascii=False)


def auth_request_js(smtp_ok_message: str) -> str:
    """Build the script that asks the server to email a login code.

    The success message is a parameter because it depends on the code lifetime.
    """
    template = AUTH_REQUEST_JS_PATH.read_text(encoding="utf-8")
    return fill_placeholders(
        template,
        {
            "__AUTH_SENDING__": _as_js_literal(AUTH_STATUS_SENDING),
            "__AUTH_SMTP_OK__": _as_js_literal(smtp_ok_message),
            "__AUTH_SMTP_FAIL__": _as_js_literal(AUTH_STATUS_SMTP_FAIL),
            "__AUTH_SMTP_PROBLEM__": _as_js_literal(AUTH_STATUS_SMTP_PROBLEM),
            "__AUTH_TOO_MANY_ATTEMPTS__": _as_js_literal(AUTH_STATUS_TOO_MANY_ATTEMPTS),
            "__AUTH_INVALID_ORIGIN__": _as_js_literal(AUTH_STATUS_INVALID_ORIGIN),
            "__AUTH_INVALID_EMAIL__": _as_js_literal(AUTH_STATUS_INVALID_EMAIL),
        },
    )


def _auth_verify_js() -> str:
    """Build the script that sends the emailed code to the server."""
    template = AUTH_VERIFY_JS_PATH.read_text(encoding="utf-8")
    return fill_placeholders(
        template,
        {
            "__AUTH_SIGNED_IN__": _as_js_literal(AUTH_STATUS_SIGNED_IN),
            "__AUTH_TOO_MANY_ATTEMPTS__": _as_js_literal(AUTH_STATUS_TOO_MANY_ATTEMPTS),
            "__AUTH_CODE_REJECTED__": _as_js_literal(AUTH_STATUS_CODE_REJECTED),
            "__AUTH_VERIFY_FAILED__": _as_js_literal(AUTH_STATUS_VERIFY_FAILED),
        },
    )


def _auth_logout_js() -> str:
    """Build the script that ends the session on the server."""
    template = AUTH_LOGOUT_JS_PATH.read_text(encoding="utf-8")
    return fill_placeholders(
        template, {"__AUTH_SIGNED_OUT__": _as_js_literal(AUTH_STATUS_SIGNED_OUT)}
    )


AUTH_REQUEST_JS = auth_request_js(AUTH_STATUS_SMTP_OK)
AUTH_VERIFY_JS = _auth_verify_js()
AUTH_LOGOUT_JS = _auth_logout_js()
