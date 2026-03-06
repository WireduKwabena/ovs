# AGENTS.md

## Project evolution

This repository is evolving from OVS (automated vetting system) into GAMS (Government Appointment Management System).

## Core rule

Extend existing modules; do not rewrite working modules.

## Reuse these subsystems

- campaigns
- cases/applications
- document verification
- AI interviews
- rubric evaluation
- audit logs
- current authentication and permissions

## New target modules

- positions
- personnel
- appointments
- approval chain
- gazette/publication

## Important constraints

- AI outputs are decision-support only, never final authority.
- Public endpoints must never expose internal vetting data.
- Prefer minimal, safe, reviewable changes.
- Inspect actual repo files before coding.
