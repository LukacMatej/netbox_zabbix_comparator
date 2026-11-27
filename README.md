# NetBox ⇄ Zabbix Sync

**Keep Zabbix monitoring in lockstep with NetBox — automatically, in real time.**

Compares device configuration between NetBox and Zabbix and creates/updates Zabbix hosts to match NetBox, driven by NetBox webhooks or an on-demand comparison run. Template and port-type selection follows a configurable priority chain (device → device role → config context), and device matching uses the Hungarian algorithm to reliably pair NetBox and Zabbix hosts even when hostnames drift.

[![CI](https://github.com/LukacMatej/netbox_zabbix_comparator/actions/workflows/ci.yml/badge.svg)](https://github.com/LukacMatej/netbox_zabbix_comparator/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.14-blue.svg)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)
![Docker](https://img.shields.io/badge/deploy-Docker-2496ED.svg)

![Compare view showing NetBox and Zabbix devices side by side with differences highlighted](docs/screenshot.png)

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Setup for Proper Application Operation](#setup-for-proper-application-operation)
  - [Priority for Selecting Templates, Port Types and Host Groups](#priority-for-selecting-templates-port-types-and-host-groups)
  - [Templates](#templates)
  - [Port Type](#port-type)
  - [Primary IP Address](#primary-ip-address)
  - [Zabbix Host Groups](#zabbix-host-groups)
  - [Custom Validation](#custom-validation)
- [REST API](#rest-api)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Features

- 🔁 **One-way sync, NetBox → Zabbix** — create, update, or leave hosts untouched based on a real diff, not a blind overwrite.
- 🪝 **Webhook-driven** — reacts to NetBox device create/update/delete events as they happen.
- 🔍 **Compare-before-you-sync UI** — review exactly what will change before triggering a sync.
- 🎯 **Hungarian-algorithm device matching** — robustly pairs NetBox and Zabbix hosts even when naming or ordering differs.
- 🧩 **Layered configuration** — templates and port types resolve from device → device role → config context, with automatic fallback.
- ✅ **Custom validation endpoint** — blocks invalid Template/Port Type combinations directly in the NetBox UI before they're saved.
- 🐳 **Single-container deployment** — ships as a small FastAPI + uvicorn Docker image.

## Architecture

```mermaid
flowchart LR
    subgraph NB[NetBox]
        DEV[Devices, Roles,\nConfig Context]
    end
    subgraph APP[netbox-zabbix sync service]
        WH["/webhook_create /webhook_update /webhook_delete"]
        CMP[Compare Engine\nHungarian matching]
        VAL["/validate_update"]
        UI[Web UI]
    end
    subgraph ZBX[Zabbix]
        HOSTS[Hosts, Templates,\nHost Groups]
    end

    NB -- webhook events --> WH
    NB -- custom field validation --> VAL
    WH --> CMP
    UI -- trigger compare / sync --> CMP
    CMP -- REST API --> NB
    CMP -- create / update hosts --> ZBX
```

## Quick Start

```bash
docker run -d \
  -p <port>:<port> \
  -e LISTEN_ADDRESS=<IP address> \
  -e HTTP_PORT=<port> \
  -e ZABBIX_DEFAULT_HOSTGROUP=<default hostgroup name> \
  -e NETBOX_IP=<NetBox IP address with http://> \
  -e NETBOX_KEY=<NetBox API key> \
  -e ZABBIX_IP=<Zabbix IP address with http://> \
  -e ZABBIX_KEY=<Zabbix API key> \
  -e PROXY_ROOT_PATH=<dev|prod> \
  netbox-zabbix
```

All necessary files (README, custom field import scripts, example `.env`) are included in the Docker image under `/doc`.

## Configuration

| Variable | Description |
|---|---|
| `LISTEN_ADDRESS` | Address the app listens on inside the container. |
| `HTTP_PORT` | Port the app listens on inside the container. |
| `ZABBIX_DEFAULT_HOSTGROUP` | Fallback Zabbix host group for synced devices. |
| `NETBOX_IP` | Base URL of the NetBox instance, including scheme (`http://`/`https://`). |
| `NETBOX_KEY` | NetBox API token. |
| `ZABBIX_IP` | Base URL of the Zabbix instance, including scheme. |
| `ZABBIX_KEY` | Zabbix API token. |
| `PROXY_ROOT_PATH` | `dev` or `prod` — adjusts routing when running behind a reverse proxy. |
| `EXCLUDED_HOSTGROUPS` | Optional. A single Zabbix host group whose hosts are dropped from comparison entirely (not shown as Zabbix-only, not matched, not synchronized). Unrelated to `ZABBIX_DEFAULT_HOSTGROUP`. Unset/empty includes all hosts. |
| `ZABBIX_AGENT_PORT` | Port for Agent interfaces (default `10050`). |
| `ZABBIX_SNMP_PORT` | Port for SNMP interfaces (default `161`). Shared by SNMPv2 and SNMPv3 — Zabbix has one port per interface type, not per SNMP version. |
| `ZABBIX_IPMI_PORT` | Port for IPMI interfaces (default `623`). |
| `ZABBIX_JMX_PORT` | Port for JMX interfaces (default `12345`). |
| `SNMPV2_MACRO` | SNMPv2 community string or Zabbix user macro (default `{$SNMP_COMMUNITY}`). |
| `ZABBIX_SNMPV3_SECURITY_NAME` | SNMPv3 security name. |
| `ZABBIX_SNMPV3_SECURITY_LEVEL` | SNMPv3 security level: `0`=noAuthNoPriv, `1`=authNoPriv, `2`=authPriv (default `2`). |
| `ZABBIX_SNMPV3_AUTH_PROTOCOL` | SNMPv3 auth protocol, Zabbix numeric code (default `1` = SHA1). |
| `ZABBIX_SNMPV3_AUTH_PASSPHRASE` | SNMPv3 auth passphrase. |
| `ZABBIX_SNMPV3_PRIV_PROTOCOL` | SNMPv3 priv protocol, Zabbix numeric code (default `1` = AES128). |
| `ZABBIX_SNMPV3_PRIV_PASSPHRASE` | SNMPv3 priv passphrase. |
| `ZABBIX_SNMPV3_CONTEXT_NAME` | SNMPv3 context name (optional). |

SNMP credentials are deployment-wide (not per-device), so they come from environment variables rather than NetBox. See Zabbix's API documentation for the full list of `authprotocol`/`privprotocol` codes.

## Setup for Proper Application Operation

### Priority for Selecting Templates, Port Types and Host Groups

Import files with custom fields and custom field choices are in the project directory and in the Docker image. Import `import_custom_fields_choices.py` first, then `import_custom_fields.py`.

The system uses a hierarchical priority when selecting Templates, Port Types and Host Groups. The application looks for values in the following order (1 = highest priority):

#### 1. Device Custom Fields (highest priority)

Set Custom Fields on individual devices:

* `zabbix_templates` - list of Zabbix templates for a specific device
* `zabbix_port_type` - port type for a specific device
* `zabbix_hostgroups` - list of Zabbix host groups for a specific device

#### 2. Device Role Custom Fields

Set Custom Fields on the device role with a selection of Custom Field Choices:

* `zabbix_templates` - list of templates for all devices with this role
* `zabbix_port_type` - port type for all devices with this role
* `zabbix_hostgroups` - list of host groups for all devices with this role

#### 3. Device Config Context (lowest priority)

In NetBox, you can set an inheritable config context for device roles, which is automatically applied to all devices with that given role:

```json
{
    "zabbix": {
        "port_type": [
            "Agent"
        ],
        "templates": [
            "Template1",
            "Template2"
        ],
        "hostgroups": [
            "Hostgroup1"
        ]
    }
}
```

**Important:** If a higher priority level contains no values (it is empty or None), the system automatically falls back to a lower priority.

### Templates

* Templates that will be applied to devices in Zabbix
* They must exist in Zabbix beforehand
* Supports multiple templates at once
* A NetBox script is available to synchronize Custom Field Choices named `zabbix_templates` with templates in Zabbix. For a similar guide, see Zabbix hostgroups.

### Port Type

* Specifies the port type for communication with Zabbix
* Supported types: Agent, SNMPv2, SNMPv3, JMX, IPMI
* Plain `SNMP` is no longer a valid choice — update the `zabbix_port_type` Custom Field Choices in NetBox to `SNMPv2`/`SNMPv3` instead. A device/role still configured with the old `SNMP` value is treated as if no port type were set until it's updated.

### Primary IP Address

* A mandatory setting in NetBox for proper operation
* Used as the connection address for the device in Zabbix
* Selected from `primary_ip4` on the device

### Zabbix Host Groups

A NetBox script is available to synchronize Custom Field Choices named `zabbix_hostgroups` with host groups in Zabbix:

* Link Custom Field Choices to a Custom Field named `zabbix_hostgroups`
* Set it as multi-select on DCIM > DEVICE and DCIM > DEVICE ROLE (role values are used when the device has none, see the priority above)
* The default host group in Zabbix is set to the value of the `ZABBIX_DEFAULT_HOSTGROUP` environment variable to keep track of all devices created by the synchronization

To install the sync scripts (templates and host groups) in [netbox-docker](https://github.com/netbox-community/netbox-docker):

* Put both scripts in the `<netbox-docker-directory>/scripts` directory
* `chmod 755 scripts`, `chmod 644 scripts/*`, `chown -R 999:999 scripts`
* In `docker-compose.yml`, add the volume `<local-path-to-scripts>:/opt/netbox/netbox/scripts:z,rw`
* In NetBox:
  * Create a data source in Operations > Data Sources (Type: Local, URL: `/opt/netbox/netbox/scripts/`) and sync it
  * Run the scripts in Customization > Scripts

### Custom Validation

Zabbix has many dependencies regarding the Port Type - Templates relationship. For this reason, a custom validation config was created to communicate with Zabbix and handle these dependencies.

* The custom validator calls the endpoint only when editing custom fields for Zabbix, see above.

##### Procedure:

Where to place `device_zabbix_validator.py` and how to reference it in `CUSTOM_VALIDATORS` depends on how NetBox itself is installed — the two setups resolve Python modules differently.

**Bare-metal / venv install**

* Place `device_zabbix_validator.py` into the NetBox root folder (`netbox/netbox/`, alongside the real `configuration.py`) — that directory is on NetBox's Python path, so the file becomes importable as a plain top-level module.
* Insert into `configuration/extra.py` (or `configuration.py` directly):

```python
CUSTOM_VALIDATORS = {
    'dcim.device': (
        'device_zabbix_validator.ZabbixCustomFieldValidator',
    )
}
```

**[netbox-docker](https://github.com/netbox-community/netbox-docker) install**

* Place `device_zabbix_validator.py` into the same host folder that's bind-mounted to `/etc/netbox/config/` (typically `configuration/`, alongside `configuration.py`/`extra.py`) — the folder is not on `sys.path` directly, though.
* netbox-docker's configuration loader (`docker/configuration.docker.py`, which becomes the real `configuration.py` inside the image) imports every `.py` file it finds in that mounted folder, but registers each one under a **flattened module name**: `netbox.configuration.<filename>` with every dot replaced by an underscore. For `device_zabbix_validator.py` that resolves to `netbox_configuration_device_zabbix_validator` — not the bare filename.
* Insert into `configuration/extra.py`:

```python
CUSTOM_VALIDATORS = {
    'dcim.device': (
        'netbox_configuration_device_zabbix_validator.ZabbixCustomFieldValidator',
    )
}
```

* Recreate the NetBox containers so the mounted config is re-read: `docker compose up -d netbox netbox-worker` (a plain `restart` won't pick up a newly-added file since it doesn't change anything Compose considers part of the container's config).

The custom validator calls the comparator's API endpoint `/validate_update` (port 7000, needs to be adjusted if a different one is used).

## REST API

Controlled via the hamburger menu:

### Compare

* Starts the comparison of devices between NetBox and Zabbix
* Displays configuration differences and matches

### Synchronize

* Starts a one-way synchronization from NetBox to Zabbix
* Possible scenarios:
  * Device exists only in NetBox → created in Zabbix
  * Device exists in both → values from NetBox overwrite values in Zabbix (if they differ)
  * Device is identical → nothing happens

### Webhooks

* App listens for webhook events from NetBox and synchronizes Zabbix accordingly
* `/webhook_create`
* `/webhook_update`
* `/webhook_delete`

## Development

```bash
# install dependencies
pip install -r requirements.txt

# run tests
python -m unittest discover -s tests -p 'test_*.py' -v

# lint (matches CI: pylint --fail-under=9, mypy on server.py + app/)
pre-commit run --all-files
```

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, lint/test commands, and PR guidelines.

## License

Released under the [MIT License](LICENSE).
