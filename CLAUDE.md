# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A FastAPI + HTMX web app that compares and synchronizes devices between NetBox (source of truth) and Zabbix (monitoring). It has three jobs:

1. **Compare**: pull devices from both systems, match them up, and show field-by-field differences (`app/compare/service/compare_service.py`).
2. **Synchronize**: push NetBox values into Zabbix — create missing hosts, update differing fields, add/remove interfaces (`app/compare/service/synchronization_service.py`).
3. **Validate**: a NetBox `CUSTOM_VALIDATORS` hook (`validators/device_zabbix_validator.py`) calls this app's `/validate_update` endpoint *before* a NetBox custom-field edit is saved, to reject changes that would break Zabbix (e.g. removing a port type that a linked template's items still require).

Tested against NetBox v4.5.2 and Zabbix v7.4.2.

## Commands

```bash
# Run the dev server (reload on, listens on 0.0.0.0:7000 by default)
python server.py --development

# Run all tests
python -m unittest discover -s tests -p 'test_*.py' -v

# Run a single test file / case
python -m unittest tests.unit_app.compare.service.test_compare_service -v
python -m unittest tests.unit_app.compare.service.test_compare_service.CompareServiceTests.test_some_case -v

# Lint (must score >= 9, matches pre-commit)
pylint --rcfile=.pylintrc server.py app

# Type check (server.py + app/ only; scripts/tests/validators are excluded)
mypy --config-file=mypy.ini server.py app

# Run all pre-commit hooks (trailing whitespace, EOF, YAML check, pylint, mypy)
pre-commit run --all-files
```

pylint's config excludes `scripts/`, `tests/`, and `validators/` (the latter lives inside a NetBox install at runtime and isn't importable standalone here). mypy only targets `server.py` and `app/`.

`app/` has no `__init__.py` files — mypy is told via `namespace_packages`/`explicit_package_bases` in `mypy.ini` to treat each subdirectory as a namespace package rooted at the repo root, matching how `app.*` imports resolve at runtime.

## Architecture

**Request flow**: `server.py` (FastAPI routes + Jinja2/HTMX templates) → `app/compare/service/` (orchestration) → `app/device/service/` (NetBox/Zabbix API calls) → `app/device/models/` (plain Python classes, not Pydantic — see `Device.get_device_fields()` which reads `__annotations__` for comparison).

- **`app/device/models/`** — `Device`, `Interface`, `Address`, `DeviceDifference`, `SyncOutput`. Plain classes with class-level type annotations (used reflectively for field comparison, not for Pydantic validation). `Device` also builds the Zabbix `host.create`/`host.update` JSON-RPC payloads.
- **`app/device/service/device_service.py`** — all read-side integration: GraphQL queries to NetBox, JSON-RPC `host.get`/`hostinterface.get` to Zabbix, plus formatting helpers (MAC, status, port type) and NetBox webhook payload parsing (`parse_webhook*`).
- **`app/device/service/validator_service.py`** — logic behind `/validate_update`. Given a NetBox custom-field change (`zabbix_port_type` / `zabbix_templates`), checks against the *existing* Zabbix host's items/interfaces (and, for new templates, the new template's items) whether the change is safe — e.g. an item hard-linked to an interface can't have that interface type removed.
- **`app/compare/service/compare_service.py`** — matches NetBox devices to Zabbix devices using a bipartite assignment (`scipy.optimize.linear_sum_assignment`) over a match-score matrix (IP match > DNS match > name match, with small tie-break bonuses for template/hostgroup overlap), then diffs matched pairs field-by-field.
- **`app/compare/service/synchronization_service.py`** — applies diffs to Zabbix (creates hosts, updates fields, adds/removes interfaces, resolves inventory-link conflicts before re-linking templates) and creates NetBox-only devices in Zabbix.
- **`app/enums/item_types.py`** — Zabbix item type IDs, used by the validator to know which item types require which interface type.
- **`server.py`** — FastAPI app; converts request JSON ↔ `Device`/`DeviceDifference` dicts (`dict_to_device`/`device_to_dict`), renders full pages or HTMX partials (based on the `hx-request` header) via `templates/`.

**Zabbix port type codes**: `1=Agent, 2=SNMP, 3=IPMI, 4=JMX`. These numeric codes and the human-readable names are used interchangeably throughout the codebase (`uniform_port_type(..., numbered=True/False)` converts between them) — when adding new code that touches interfaces, check which form the surrounding function expects.

**Priority resolution for NetBox → Zabbix config** (templates and port type): device custom fields > device role custom fields > device config context. Implemented via `get_nb_templates`/`get_port_types` in `device_service.py`; see README.md for the full user-facing explanation, including where `device_zabbix_validator.py` needs to be placed for bare-metal vs. netbox-docker installs.

**Credentials/config** come from environment variables only (`NETBOX_IP`, `NETBOX_KEY`, `ZABBIX_IP`, `ZABBIX_KEY`, `ZABBIX_DEFAULT_HOSTGROUP`, `LISTEN_ADDRESS`, `HTTP_PORT`, `PROXY_ROOT_PATH`) — no config file or secrets manager. `server.py`'s `test_connection()` fails fast at startup if NetBox/Zabbix aren't reachable.

**Webhooks**: NetBox webhooks (`/webhook_create`, `/webhook_update`, `/webhook_delete`) drive one-device incremental sync, separate from the manual `/run_comparison(_sync)` bulk flow.

## CI

`.gitlab-ci.yml` runs `pre-commit run --all-files` (lint stage) and `python -m unittest discover -s tests -p 'test_*.py' -v` (test stage) on every push, then builds/publishes a Docker image and deploys on tags.
