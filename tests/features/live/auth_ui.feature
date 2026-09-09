@live_server @live_ui
Feature: Live observatory authentication chrome
  Gradio login row, Enviar/Clear while logged out, and IMAP verify in Chromium.

  Scenario: Logged-out load shows login
    Given the observatory is shown without a session
    When the user looks at the observatory
    Then an observatory email field and send-code control are visible
    And the observatory question input remains on the same screen

  Scenario: Enviar while logged out
    Given the observatory is shown without a session
    When the user sends an observatory question
    Then an observatory Spanish notice tells them to sign in
    And the observatory citation inspector is not shown
    And the observatory conversation does not show a CAMEX clause

  Scenario: Clear while logged out keeps turns
    Given a cloned authenticated observatory with a prior turn
    And the user has logged out of the observatory
    When the user clicks observatory Clear
    Then those prior observatory turns remain
    And an observatory Spanish notice tells them to sign in

  Scenario: Login with mailed code
    Given the observatory is shown without a session
    When the user requests a live code, reads it from IMAP, and verifies
    Then an observatory logout control is visible
    And the observatory request-code fields are not shown

  Scenario: Logout returns the login row
    Given a cloned authenticated observatory with a prior turn
    When the user logs out of the observatory
    Then the observatory login row is visible again
    And observatory staff chrome is not shown
    And prior observatory turns remain until Clear
