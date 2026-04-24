# AGENTS.md

## Purpose
This file defines the coding and commit conventions for AI agents working in this repository.

## Coding style
- Keep functions small and focused.
- Add or update tests when behavior changes.
- Prefer explicit errors with actionable messages.
- Keep README examples aligned with code changes.

## Commit style (required)
- Use **gitmoji** in every commit subject.
- Format: `<gitmoji> <short imperative summary>`
- Examples:
  - `✨ Add SysMLv2 validator tool`
  - `🐛 Fix fallback command detection`
  - `✅ Add tests for file validation`
  - `📝 Update README usage section`

## Pre-commit checks
Run these before finishing:
- `python -m unittest discover -s tests -v`
- `python -m compileall src tests`
