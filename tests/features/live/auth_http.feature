@live_server @live_http
Feature: Live HTTP authentication
  Allowlisted one-time secret through real mail, then an HTTP session cookie.

  Scenario: Allowlisted mailbox receives a 6-digit secret
    Given an authenticated live HTTP session
    Then the live mailbox secret is six digits in the body not the subject

  Scenario: Allowlist miss sends no live message
    Given a live IMAP mailbox without a session credential
    When a live client requests a one-time secret for "stranger@example.com"
    Then the live OTP request shape matches success
    And no new live one-time-secret message arrives

  Scenario: Correct code authenticates
    Given an authenticated live HTTP session
    When the live client probes the session
    Then the live session probe reports that mailbox
    And the live session cookie is HttpOnly

  Scenario: Secret is single-use
    Given an authenticated live HTTP session
    When the live client submits that secret again after the verify interval
    Then the live client is not authenticated from that secret

  Scenario: Logout blocks later chat
    Given an authenticated live HTTP session
    When the live client logs out on a cloned client
    Then a later live chat request is HTTP 401
    And the shared live session remains authenticated

  Scenario: Probe without a session
    Given no live HTTP session credential
    When the live client probes the session
    Then the live session probe reports unauthenticated
    And the live probe status is not HTTP 401

  Scenario: Unauthenticated chat is 401
    Given no live HTTP session credential
    When the live client posts a CAMEX question
    Then the response is HTTP 401

  Scenario: Unauthenticated clear is 401
    Given no live HTTP session credential
    When the live client posts chat-clear with a session id
    Then the response is HTTP 401

  Scenario: Health stays public
    Given no live HTTP session credential
    When the live client requests health
    Then the live health response is HTTP 200
    And live health dump fields are present
