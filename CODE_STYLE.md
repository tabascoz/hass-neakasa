# Code Style Guide

Style conventions for the `hass-neakasa` project. Run
`uv run ruff format .`, `uv run ruff check . --fix` and
`uv run mypy custom_components/neakasa` before committing — they must
exit cleanly. `uv run pytest` follows.

**Always read this file before adding or restructuring code.**

## Quality scale target

This integration applies the **Bronze/Silver/Gold** rules of the
[Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
that are pertinent to it; Platinum is an aspiration, not a claim.
Each tier inherits every rule from the previous one:

- **Bronze** — UI setup via `config_flow`, config-flow tests, user-facing docs.
- **Silver** — active code owner, automatic recovery from connection errors,
  reauth flow, no log spam on transient failures.
- **Gold** — full test coverage, entity translations, reconfigure flow,
  diagnostics download, optional discovery.
- **Platinum** — strict typing, fully async code base, efficient data handling
  (no redundant polling or state-machine writes).

`quality_scale.yaml` at the integration root lists each rule as
`done` / `todo` / `exempt` (with a reason) and must stay **honest**: a rule is
`done` only when the code actually implements it. Update the file in the same
PR that satisfies (or removes) a rule.

## Language

- Code is written in **English**: file names, class names, function names,
  variable names, dictionary keys, identifier strings.
- User-facing strings live in `custom_components/neakasa/translations/{en,de,pl}.json`
  only — never hardcoded in Python.

## File organization

- **One top-level class per file.** Multiple semantically related classes get
  grouped into a package directory with one class per submodule and an
  `__init__.py` re-exporting the public symbols.
- **`__init__.py` of the integration package** wires `async_setup_entry`,
  `async_unload_entry`, `async_reload_entry` and nothing else.

## Entities: one class per entity

- **One class per entity.** Every entity gets its own dedicated class — never
  share a generic class parameterized by a key string or options list.
  Encode the entity's behaviour directly in its class via `@property` and
  class-level `_attr_*` constants.
- The reason: each entity is a discrete contract; mixing them through a
  generic class hides the contract behind indirection and discourages per-entity
  refinement.

## Naming

- Public classes are prefixed with `Neakasa`.
- Concrete platform entities end with the entity type:
  `NeakasaSensor`, `NeakasaBinarySensor`, `NeakasaSwitch`.
- Exception classes end with `Error`: `NeakasaApiClientError`,
  `NeakasaApiClientCommunicationError`, `NeakasaApiClientAuthenticationError`.
- Private attributes / functions are prefixed with `_`.

## Typing

**Prefer typed shapes over bare dicts/lists.** The `data/` package (when added)
will hold `TypedDict` config shapes and `@dataclass` runtime records.

Until full strict typing is achieved:

- Use `@dataclass` for structured records.
- Use `TypedDict` for known dict shapes.
- Avoid `typing.Any` — use `dict[str, Any]` only at HA framework boundaries.
- Add `# type: ignore[override]` with a comment when narrowing HA callback signatures.

## Properties and `__init__`

- **Always prefer `@property`** over assigning `_attr_*` values in `__init__`.
- When the body of `__init__` would only call `super().__init__(...)`, omit
  `__init__` entirely.
- Class-level constants like `_attr_has_entity_name = True` are fine.

## Imports

- Always start every module with `from __future__ import annotations`.
- Same-package relative imports (`from .module import …`) are the default.
- Move type-only imports into a `TYPE_CHECKING` block when possible.

## Docstrings

- Every public class, function, method and `__init__` has a docstring.
- A single sentence is usually enough. Describe the *contract* or the *why*.

## Comments

- Default to **no comments**. Add one only when the *why* is not obvious from
  the code: a hidden constraint, a workaround, a subtle invariant.
- Never describe *what* the code does — well-named identifiers handle that.
- **No section dividers** (e.g. `# --- API payloads ---`). Split the file instead.

## Logging

- Use the package-level `_LOGGER` from `const.py`; never call `logging.getLogger(...)`
  ad-hoc.
- Use **lazy `%`-formatting**, never f-strings:

  ```python
  _LOGGER.warning("Refresh failed: %s", exception)   # ✓
  _LOGGER.warning(f"Refresh failed: {exception}")    # ✗
  ```

- Levels:
  - `debug` — successful fetch summaries, every-poll diagnostics.
  - `info` — one-shot lifecycle events.
  - `warning` — recoverable failures.
  - `error` / `exception` — unrecoverable; pair `exception` with caught exceptions.
- Never log secrets (`token`, `password`, `key`, full headers).

## Error messages

- Format: `"Failed to <verb> <object>: <cause>"`.
- Pre-validate inputs before the network call.
- Custom exceptions follow a hierarchy:
  `NeakasaApiClientError` (base) → `NeakasaApiClientCommunicationError` and
  `NeakasaApiClientAuthenticationError`.

## Pre-commit hooks

`pre-commit` is a dev dependency and `.pre-commit-config.yaml` mirrors the
lint commands. Install once per clone:

```bash
uv run pre-commit install
```

## Conventional commits

All commits follow [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Meaning | Bump |
|---|---|---|
| `feat` | New feature | minor |
| `fix` | Bug fix | patch |
| `perf` | Performance improvement | patch |
| `deps` | Dependency bump | patch |
| `docs` | Documentation only | none |
| `refactor` | Refactor without behavior change | none |
| `test` | Test-only change | none |
| `ci` | CI / tooling change | none |
| `chore` | Anything else | none |

- Subject line: imperative mood, lowercase, no trailing period.
- Use scopes when useful: `fix(sensor): map missing values to None`.
- A `BREAKING CHANGE:` footer (or `!` after type) bumps the major version.

## Linting and verification

- Ruff configuration lives in `pyproject.toml` (`[tool.ruff]`).
- Mypy configuration lives in `pyproject.toml` (`[tool.mypy]`).
- After every change run `uv run ruff format .`, `uv run ruff check . --fix`,
  and `uv run mypy custom_components/neakasa`.
- Tests live in `tests/`, mirroring the production layout.