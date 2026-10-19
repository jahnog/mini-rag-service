from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import pytest
from playwright.sync_api import Route
from pytest_bdd import given, parsers, then, when

from bcra_rag.ui.config import (
    AUTH_NOTICE,
    AUTH_STATUS_CODE_REJECTED,
    AUTH_STATUS_INVALID_EMAIL,
    AUTH_STATUS_INVALID_ORIGIN,
    AUTH_STATUS_SMTP_FAIL,
    AUTH_STATUS_SMTP_PROBLEM,
    AUTH_STATUS_TOO_MANY_ATTEMPTS,
    CANNED_PROMPTS,
    LAYOUT_STAFF,
    LAYOUT_USER,
)
from tests.features.live.browser import (
    NARROW,
    WIDE,
    bounding,
    click_id,
    field,
    select_vista,
    send_observatory_question,
    visible,
)
from tests.features.live.http_client import raise_for_limiter
from tests.features.live.mailbox import consume_used, wait_for_new_otp

UiWorld = dict[str, Any]
_STATE: dict[str, Any] = {}

STAFF_CHROME = (
    "#observatory-freeze",
    "#observatory-side",
    "#trust-panel",
    "#l1-panel",
)


@given("the observatory is shown without a session", target_fixture="ui_world")
def observatory_logged_out(logged_out_observatory: UiWorld) -> UiWorld:
    return dict(logged_out_observatory)


@given("a cloned authenticated observatory with a prior turn", target_fixture="ui_world")
def observatory_cloned(cloned_observatory: UiWorld) -> UiWorld:
    return dict(cloned_observatory)


@given("an authenticated observatory session with a prior turn", target_fixture="ui_world")
def observatory_shared(shared_observatory: UiWorld) -> UiWorld:
    return dict(shared_observatory)


@given("the user has logged out of the observatory")
def observatory_logout_given(ui_world: UiWorld) -> None:
    _logout(ui_world)


@given("the observatory is in the end-user layout")
def observatory_usuario(ui_world: UiWorld) -> None:
    select_vista(ui_world["page"], LAYOUT_USER)


@given("the observatory is in the staff layout")
def observatory_staff(ui_world: UiWorld) -> None:
    select_vista(ui_world["page"], LAYOUT_STAFF)


@given("the observatory is shown on a wide viewport")
def observatory_wide(ui_world: UiWorld) -> None:
    ui_world["page"].set_viewport_size(WIDE)
    select_vista(ui_world["page"], LAYOUT_STAFF)


@given("the observatory is shown on a narrow viewport")
def observatory_narrow(ui_world: UiWorld) -> None:
    ui_world["page"].set_viewport_size(NARROW)
    select_vista(ui_world["page"], LAYOUT_STAFF)


@given("observatory health reports index_ready true")
def observatory_index_ready(ui_world: UiWorld, live_http_session: dict[str, Any]) -> None:
    response = live_http_session["client"].get("/health")
    raise_for_limiter(response, what="GET /health")
    if not response.json().get("index_ready"):
        pytest.skip("live health reports index_ready false")


@when("the user looks at the observatory")
def user_looks(ui_world: UiWorld) -> None:
    ui_world["page"].locator("#observatory-shell").wait_for()


@when("the user sends an observatory question")
def user_enviar(ui_world: UiWorld) -> None:
    send_observatory_question(ui_world["page"], "Qué dice la Comunicación A 3500?")


@when("the user clicks observatory Clear")
def user_clear(ui_world: UiWorld) -> None:
    click_id(ui_world["page"], "observatory-clear")
    ui_world["page"].locator("#observatory-chat").wait_for()


@when("the user requests a live code, reads it from IMAP, and verifies")
def user_login_imap(ui_world: UiWorld, live_http_session: dict[str, Any]) -> None:
    page = ui_world["page"]
    email = live_http_session["email"]
    mailbox = live_http_session["mailbox"]
    field(page, "auth-email").fill(email)
    if live_http_session.get("otp_sent"):
        time.sleep(60)
    clicked = datetime.now(UTC)
    click_id(page, "auth-send")
    mail = wait_for_new_otp(mailbox, since=clicked)
    field(page, "auth-code").fill(mail.code)
    click_id(page, "auth-verify")
    page.locator("#auth-logout").wait_for()
    consume_used(mailbox, mail)


@given(parsers.parse("the send-code endpoint returns {outcome}"))
def stub_send_code(ui_world: UiWorld, outcome: str) -> None:
    def respond(route: Route) -> None:
        if outcome == "network":
            route.abort()
        else:
            route.fulfill(status=int(outcome), json={})

    ui_world["page"].route("**/auth/request", respond)


@when("the user requests a stubbed observatory code")
def request_stubbed_code(ui_world: UiWorld) -> None:
    field(ui_world["page"], "auth-email").fill("operator@example.com")
    click_id(ui_world["page"], "auth-send")


@then(parsers.parse("the send-code notice for {outcome} stays beyond the old reset interval"))
def persistent_send_notice(ui_world: UiWorld, outcome: str) -> None:
    expected = {
        "200": "Listo. Si pediste un código",
        "403": AUTH_STATUS_INVALID_ORIGIN,
        "422": AUTH_STATUS_INVALID_EMAIL,
        "429": AUTH_STATUS_TOO_MANY_ATTEMPTS,
        "503": AUTH_STATUS_SMTP_FAIL,
        "500": AUTH_STATUS_SMTP_PROBLEM,
        "network": AUTH_STATUS_SMTP_PROBLEM,
    }[outcome]
    page = ui_world["page"]
    notice = page.locator("#auth-status")
    notice.get_by_text(expected, exact=False).wait_for()
    original = notice.inner_text()
    page.wait_for_timeout(2200)
    assert notice.inner_text() == original


@then("the observatory send-code control is enabled")
def send_code_enabled(ui_world: UiWorld) -> None:
    root = ui_world["page"].locator("#auth-send")
    button = root.locator("button")
    assert (button.first if button.count() else root).is_enabled()


@when("the user verifies a stubbed invalid observatory code")
def verify_stubbed_code(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    page.route("**/auth/verify", lambda route: route.fulfill(status=401, json={}))
    field(page, "auth-code").fill("000000")
    click_id(page, "auth-verify")


@then("the code-rejected notice replaces the send-code notice")
def rejected_code_notice(ui_world: UiWorld) -> None:
    ui_world["page"].get_by_text(AUTH_STATUS_CODE_REJECTED, exact=True).wait_for()


@when("the user logs out of the observatory")
def user_logout(ui_world: UiWorld) -> None:
    _logout(ui_world)


@when("the user selects the staff observatory layout")
def user_selects_staff(ui_world: UiWorld) -> None:
    select_vista(ui_world["page"], LAYOUT_STAFF)


@when("the user selects the usuario observatory layout")
def user_selects_usuario(ui_world: UiWorld) -> None:
    select_vista(ui_world["page"], LAYOUT_USER)


@when("the user asks a named Com. A that is in the dump from the observatory")
def user_asks_a3500(ui_world: UiWorld) -> None:
    body = send_observatory_question(
        ui_world["page"], "Qué dice la Comunicación A 3500?"
    )
    ui_world["last_chat"] = body
    _STATE["a3500"] = body
    _apply_a3500_matrix(body)


@when("the user looks at the last in-corpus observatory answer")
def user_looks_incorus(ui_world: UiWorld) -> None:
    body = _STATE.get("a3500")
    if body is None:
        body = send_observatory_question(
            ui_world["page"], "Qué dice la Comunicación A 3500?"
        )
        _STATE["a3500"] = body
    ui_world["last_chat"] = body
    _apply_a3500_matrix(body)


@when("the user asks what Comunicación A 9999 says from the observatory")
def user_asks_a9999(ui_world: UiWorld, live_http_session: dict[str, Any]) -> None:
    health = live_http_session["client"].get("/health")
    raise_for_limiter(health, what="GET /health")
    if not health.json().get("index_ready"):
        pytest.skip("live health reports index_ready false")
    body = send_observatory_question(
        ui_world["page"], "Qué dice la Comunicación A 9999?"
    )
    ui_world["last_chat"] = body


@then("an observatory email field and send-code control are visible")
def login_fields_visible(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert field(page, "auth-email").is_visible()
    assert visible(page, "#auth-send")


@then("the observatory question input remains on the same screen")
def question_visible(ui_world: UiWorld) -> None:
    assert field(ui_world["page"], "observatory-input").is_visible()


@then("an observatory Spanish notice tells them to sign in")
def auth_notice_visible(ui_world: UiWorld) -> None:
    ui_world["page"].get_by_text(AUTH_NOTICE, exact=False).wait_for()


@then("the observatory citation inspector is not shown")
def inspector_hidden(ui_world: UiWorld) -> None:
    assert not visible(ui_world["page"], "#observatory-side")


@then("the observatory conversation does not show a CAMEX clause")
def no_camex_clause(ui_world: UiWorld) -> None:
    text = ui_world["page"].locator("#observatory-chat").inner_text()
    assert "Fuente:" not in text
    assert "A3500" not in text


@then("those prior observatory turns remain")
def prior_turns(ui_world: UiWorld) -> None:
    seed = ui_world.get("seed") or "Madrid"
    assert visible(ui_world["page"], f"#observatory-chat >> text={seed}") or (
        seed in ui_world["page"].locator("#observatory-chat").inner_text()
    )


@then("an observatory logout control is visible")
def logout_visible(ui_world: UiWorld) -> None:
    assert visible(ui_world["page"], "#auth-logout")


@then("the observatory request-code fields are not shown")
def request_fields_hidden(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert not field(page, "auth-email").is_visible()


@then("the observatory login row is visible again")
def login_row_back(ui_world: UiWorld) -> None:
    assert field(ui_world["page"], "auth-email").is_visible()
    assert visible(ui_world["page"], "#auth-send")


@then("observatory staff chrome is not shown")
def staff_chrome_hidden_simple(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    for selector in STAFF_CHROME:
        assert not visible(page, selector)
    assert not visible(page, ".thought-group")


@then("prior observatory turns remain until Clear")
def prior_turns_until_clear(ui_world: UiWorld) -> None:
    prior_turns(ui_world)


@then("freeze chips, inspector, trust panel, and Calidad L1 are not shown")
def default_usuario_chrome(ui_world: UiWorld) -> None:
    staff_chrome_hidden_simple(ui_world)


@then("the observatory question input, send, Clear, and suggested prompts are visible")
def main_controls_visible(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert field(page, "observatory-input").is_visible()
    assert visible(page, "#observatory-send")
    assert visible(page, "#observatory-clear")
    for prompt in CANNED_PROMPTS:
        assert page.get_by_text(prompt, exact=False).count() > 0


@then("freeze chips, inspector, trust, Calidad L1, and thinking stay hidden")
def unauth_staff_chrome(ui_world: UiWorld) -> None:
    staff_chrome_hidden_simple(ui_world)


@then("observatory freeze chips and the side inspector are shown")
def staff_chrome_shown(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert visible(page, "#observatory-freeze")
    assert visible(page, "#observatory-side")


@then("observatory freeze chips and the side inspector are hidden")
def staff_chrome_hidden_after_user(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert not visible(page, "#observatory-freeze")
    assert not visible(page, "#observatory-side")


@then("the four canned CAMEX examples are shown")
def canned_shown(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert len(CANNED_PROMPTS) == 4
    for prompt in CANNED_PROMPTS:
        assert page.get_by_text(prompt, exact=False).count() > 0


@then("one canned prompt asks for Comunicación A 9999")
def canned_has_9999(ui_world: UiWorld) -> None:
    assert any("A 9999" in prompt for prompt in CANNED_PROMPTS)
    assert ui_world["page"].get_by_text("A 9999", exact=False).count() > 0


@then("none is a generic explain the BCRA prompt")
def canned_not_generic(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert page.get_by_text("explain the BCRA", exact=False).count() == 0
    for prompt in CANNED_PROMPTS:
        assert "explain the BCRA" not in prompt.lower()


@then("the observatory conversation shows the answer")
def conversation_has_answer(ui_world: UiWorld) -> None:
    text = ui_world["page"].locator("#observatory-chat").inner_text()
    assert text.strip()


@then("the observatory thinking region is not shown")
def thinking_hidden(ui_world: UiWorld) -> None:
    assert not visible(ui_world["page"], ".thought-group")


@then("the observatory answer, citation cards, and trust log are on the same screen")
def staff_incorus_chrome(ui_world: UiWorld) -> None:
    page = ui_world["page"]
    assert ui_world["page"].locator("#observatory-chat").inner_text().strip()
    assert visible(page, "#citation-card") or visible(page, "#observatory-side")
    assert visible(page, "#trust-panel")


@then("if an observatory thinking region is shown it does not contain Fuente")
def thinking_no_fuente(ui_world: UiWorld) -> None:
    loc = ui_world["page"].locator(".thought-group")
    if loc.count() == 0:
        return
    assert "Fuente:" not in loc.inner_text()


@then("an observatory abstain banner is visible in the chat stage")
def abstain_banner(ui_world: UiWorld) -> None:
    assert visible(ui_world["page"], "#abstain-banner")


@then("the observatory chat stage is on the left")
def chat_left(ui_world: UiWorld) -> None:
    stage = bounding(ui_world["page"], "#observatory-stage")
    side = bounding(ui_world["page"], "#observatory-side")
    assert stage["x"] < side["x"]


@then("the observatory inspector is on the right")
def inspector_right(ui_world: UiWorld) -> None:
    stage = bounding(ui_world["page"], "#observatory-stage")
    side = bounding(ui_world["page"], "#observatory-side")
    assert side["x"] >= stage["x"] + stage["width"] * 0.3


@then("the observatory session card is on the right")
def session_card_right(ui_world: UiWorld) -> None:
    stage = bounding(ui_world["page"], "#observatory-stage")
    card = bounding(ui_world["page"], "#auth-login")
    assert card["x"] >= stage["x"] + stage["width"] * 0.3


@then("the observatory inspector sits below the chat stage")
def inspector_below(ui_world: UiWorld) -> None:
    stage = bounding(ui_world["page"], "#observatory-stage")
    side = bounding(ui_world["page"], "#observatory-side")
    assert side["y"] >= stage["y"] + stage["height"] * 0.4


def _logout(ui_world: UiWorld) -> None:
    click_id(ui_world["page"], "auth-logout")
    field(ui_world["page"], "auth-email").wait_for()


def _apply_a3500_matrix(body: dict[str, Any] | None) -> None:
    if not body:
        pytest.fail("observatory chat did not return JSON")
    if body.get("finding") == "silencio":
        detail = _skippable_a3500_detail(body)
        if detail is not None:
            pytest.skip(f"HTTP finding is silencio ({detail})")
        pytest.fail("HTTP finding is silencio")
    ids = [item.get("id") for item in body.get("citations") or []]
    if "A3500" not in ids:
        pytest.fail("named Com. A 3500 did not return citation id A3500")


_SKIP_A3500_DETAILS = frozenset({"no hay modelo disponible", "falta el documento"})


def _skippable_a3500_detail(body: dict[str, Any]) -> str | None:
    for row in body.get("guardrails") or []:
        if row.get("rule") != "generate" or row.get("verdict") != "skipped":
            continue
        detail = str(row.get("detail") or "")
        if detail in _SKIP_A3500_DETAILS:
            return detail
    return None
