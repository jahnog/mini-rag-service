@live_server @live_ui
Feature: Live observatory layouts
  Usuario vs Staff chrome, canned prompts, inspector, abstain banner, viewports.

  Scenario: Default load is Usuario
    Given the observatory is shown without a session
    When the user looks at the observatory
    Then freeze chips, inspector, trust panel, and Calidad L1 are not shown
    And the observatory question input, send, Clear, and suggested prompts are visible

  Scenario: Unauthenticated staff selection does not reveal chrome
    Given the observatory is shown without a session
    When the user selects the staff observatory layout
    Then freeze chips, inspector, trust, Calidad L1, and thinking stay hidden

  Scenario: Switch to Staff then Usuario keeps the session
    Given an authenticated observatory session with a prior turn
    When the user selects the staff observatory layout
    Then observatory freeze chips and the side inspector are shown
    When the user selects the usuario observatory layout
    Then observatory freeze chips and the side inspector are hidden
    And prior observatory turns remain until Clear

  Scenario: Suggested prompts mix canned examples and silencio
    Given the observatory is shown without a session
    When the user looks at the observatory
    Then the four canned CAMEX examples are shown
    And one canned prompt asks for Comunicación A 9999
    And none is a generic explain the BCRA prompt

  Scenario: Usuario in-corpus hides inspector
    Given an authenticated observatory session with a prior turn
    And the observatory is in the end-user layout
    And observatory health reports index_ready true
    When the user asks a named Com. A that is in the dump from the observatory
    Then the observatory conversation shows the answer
    And the observatory citation inspector is not shown
    And the observatory thinking region is not shown

  Scenario: Staff in-corpus shows inspector
    Given an authenticated observatory session with a prior turn
    And the observatory is in the staff layout
    And observatory health reports index_ready true
    When the user looks at the last in-corpus observatory answer
    Then the observatory answer, citation cards, and trust log are on the same screen
    And if an observatory thinking region is shown it does not contain Fuente

  Scenario: Staff silencio banner
    Given an authenticated observatory session with a prior turn
    And the observatory is in the staff layout
    When the user asks what Comunicación A 9999 says from the observatory
    Then an observatory abstain banner is visible in the chat stage

  Scenario: Wide layout keeps chat dominant
    Given an authenticated observatory session with a prior turn
    And the observatory is in the staff layout
    And the observatory is shown on a wide viewport
    When the user looks at the observatory
    Then the observatory chat stage is on the left
    And the observatory inspector is on the right

  Scenario: Narrow layout stacks the inspector
    Given an authenticated observatory session with a prior turn
    And the observatory is in the staff layout
    And the observatory is shown on a narrow viewport
    When the user looks at the observatory
    Then the observatory inspector sits below the chat stage
