## Purpose

Send cookieless observatory page views to a configured analytics collector so operators can see public visits, without tracking mail-link pages, mailboxes, or question text, and without requiring a collector in default tests.

## ADDED Requirements

### Requirement: Optional cookieless page view
When a tracker origin and a numeric site id are both configured and valid, the observatory page SHALL send a cookieless page view to that collector, honor Do Not Track, and record time on the page. The page MUST NOT send a mailbox or question text. When either value is unset or invalid, the observatory MUST NOT load the collector script, and the assistant MUST still render. Loopback hosts MUST NOT send a page view unless the operator forces tracking with a query flag. Mail-link pages MUST NOT send a page view. Default automated tests MUST NOT require a live collector.

#### Scenario: Unset collector still renders
- **GIVEN** no tracker origin is configured
- **WHEN** the observatory page is built
- **THEN** the page does not load a collector script
- **AND** the assistant still renders

#### Scenario: Invalid collector is omitted
- **GIVEN** a tracker origin that is not an https origin, or a site id that is not numeric
- **WHEN** the observatory page is built
- **THEN** the page does not load a collector script

#### Scenario: Configured collector sends a page view
- **GIVEN** a valid https tracker origin and a numeric site id
- **WHEN** the observatory page is built
- **THEN** the page includes a cookieless page-view script for that origin and site id
- **AND** the script honors Do Not Track
- **AND** the script does not include a mailbox or question text

#### Scenario: Loopback does not send
- **GIVEN** a valid https tracker origin and a numeric site id
- **AND** the observatory is opened on a loopback host
- **WHEN** the page runs without a force-tracking query flag
- **THEN** it does not load the collector script

#### Scenario: Mail-link pages stay untracked
- **GIVEN** a valid https tracker origin and a numeric site id
- **WHEN** a mail-link confirm or fail page is shown
- **THEN** that page does not load a collector script
