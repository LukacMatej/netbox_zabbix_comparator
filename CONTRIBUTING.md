# Contributing

Thanks for considering a contribution to NetBox ⇄ Zabbix Sync.

## Development setup

```bash
git clone https://github.com/LukacMatej/netbox_zabbix_comparator.git
cd netbox_zabbix_comparator
pip install -r requirements.txt
pip install pre-commit
pre-commit install
```

Copy `env.list` and fill in a NetBox/Zabbix test instance to run the app locally:

```bash
uvicorn server:app --host 0.0.0.0 --port 7000
```

## Before opening a PR

Run the same checks CI runs:

```bash
# lint (pylint --fail-under=9, mypy on server.py + app/)
pre-commit run --all-files

# tests
python -m unittest discover -s tests -p 'test_*.py' -v
```

Both must pass — CI (`.github/workflows/ci.yml`) enforces the same two steps on every push and PR.

## Branching & commits

* Branch names follow `<issue-number>-<short-description>`, e.g. `34-upravy-kodu-pro-produkci`.
* Keep commits focused; describe *why* a change was made when it isn't obvious from the diff.

## Pull requests

* Target `main`.
* Include a short description of the change and, for behavior changes, how you verified it (test output, manual steps against a NetBox/Zabbix instance).
* Update `README.md` if the change affects configuration, setup, or the API surface.

## Reporting issues

Open a GitHub issue with:

* NetBox and Zabbix versions involved
* Steps to reproduce
* Expected vs. actual behavior
* Relevant log output (redact API keys/tokens)
