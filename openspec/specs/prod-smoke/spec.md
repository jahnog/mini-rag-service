# prod-smoke Specification

## Purpose

Exercise the public origin on a daily schedule and notify operators about every completed run — success, failure, or schedule-bound cutoff — without mailing skipped overlaps or hand-invoked runs.

## Requirements

### Requirement: Daily production smoke mails on every completed run
When the daily production-smoke schedule finishes a run against the public origin, it SHALL send mail to the configured notify address, or to the live mailbox when that notify address is unset. That mail SHALL be sent when the run succeeds and when the run fails, including when the run is cut off by the schedule bound. The subject SHALL distinguish success, failure, and a run cut off by that bound. A skipped overlapping run that did not start MUST NOT send that mail. The production-smoke command invoked by hand MUST NOT send that mail. The schedule’s own unix-user mail MUST remain disabled.

#### Scenario: Successful daily run mails
- **GIVEN** the daily production-smoke schedule finished a run
- **AND** that run succeeded
- **WHEN** notify mail is sent
- **THEN** the configured notify address (or the live mailbox) receives one message
- **AND** the subject names success

#### Scenario: Failed daily run mails
- **GIVEN** the daily production-smoke schedule finished a run
- **AND** that run failed
- **WHEN** notify mail is sent
- **THEN** the configured notify address (or the live mailbox) receives one message
- **AND** the subject names failure

#### Scenario: Bound-cut daily run mails
- **GIVEN** the daily production-smoke schedule started a run
- **AND** the schedule bound cut the run off
- **WHEN** notify mail is sent
- **THEN** the configured notify address (or the live mailbox) receives one message
- **AND** the subject names that the run was cut off

#### Scenario: Overlapping skip does not mail
- **GIVEN** a daily production-smoke run is already in progress
- **WHEN** the schedule ticks again
- **THEN** the overlapping start is skipped
- **AND** no notify mail is sent for that skip

#### Scenario: Hand-invoked production smoke does not mail
- **GIVEN** the operator invoked the production-smoke command by hand
- **WHEN** that command finishes
- **THEN** the daily notify mail is not sent
