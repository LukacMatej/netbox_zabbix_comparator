# Netbox and Zabbix Device Comparison and Synchronization

The application is used to synchronize device configurations between Netbox and Zabbix, featuring the ability to compare and automatically create/update devices in Zabbix based on the configuration in Netbox.

## Running Docker

```bash
docker run -d \
  -p <port>:<port> \
  -e LISTEN_ADDRESS=<IP address> \
  -e HTTP_PORT=<port> \
  -e ZABBIX_DEFAULT_HOSTGROUP=<default hostgroup name> \
  -e EXCLUDED_HOSTGROUPS=<Zabbix hostgroup name to exclude from comparison> \
  -e NETBOX_IP=<Netbox IP address with http://> \
  -e NETBOX_KEY=<Netbox API key> \
  -e ZABBIX_IP=<Zabbix IP address with http://> \
  -e ZABBIX_KEY=<Zabbix API key> \
  -e PROXY_ROOT_PATH=<dev|prod>
  netbox-zabbix

```

## Setup for Proper Application Operation

### Priority for Selecting Templates and Port Types

The system uses a hierarchical priority when selecting Templates and Port Types. The application looks for values in the following order (1 = highest priority):

#### 1. Device Custom Fields (highest priority)

Set Custom Fields on individual devices:

* `zabbix_templates` - list of Zabbix templates for a specific device
* `zabbix_port_type` - port type for a specific device

#### 2. Device Role Custom Fields

Set Custom Fields on the device role with a selection of Custom Field Choices:

* `zabbix_templates` - list of templates for all devices with this role
* `zabbix_port_type` - port type for all devices with this role

#### 3. Device Config Context (lowest priority)

In Netbox, you can set an inheritable config context for device roles, which is automatically applied to all devices with that given role:

```json
{
    "zabbix": {
        "port_type": [
            "Agent"
        ],
        "templates": [
            "Template1",
            "Template2"
        ]
    }
}

```

**Important:** If a higher priority level contains no values (it is empty or None), the system automatically falls back to a lower priority.

### Templates

* Templates that will be applied to devices in Zabbix
* They must exist in Zabbix beforehand
* Supports multiple templates at once
* A Netbox script is available to synchronize Custom Field Choices named `zabbix_templates` with templates in Zabbix. For a similar guide, see Zabbix hostgroups.

### Port Type

* Specifies the port type for communication with Zabbix
* Supported types: Agent, SNMP, JMX, IPMI

### Primary IP Address

* A mandatory setting in Netbox for proper operation
* Used as the connection address for the device in Zabbix
* Selected from `primary_ip4` on the device

### Zabbix Host Groups

A Netbox script is available to synchronize Custom Field Choices named `zabbix_hostgroups` with host groups in Zabbix:

* Link Custom Field Choices to a Custom Field named `zabbix_hostgroups`
* Set it as multi-select on DCIM > DEVICE
* The default host group in Zabbix is set to "Netbox" to keep track of all devices created by the synchronization

### Excluded Hostgroups

* `EXCLUDED_HOSTGROUPS` optionally names a single Zabbix hostgroup to exclude from comparison
* Zabbix hosts belonging to that hostgroup are dropped from the comparison results entirely (they are neither shown as "Zabbix-only", nor matched against NetBox, nor synchronized)
* This is unrelated to `ZABBIX_DEFAULT_HOSTGROUP`, which only controls which hostgroup a newly-created Zabbix host is assigned to
* Leave unset (or empty) to include all hosts

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

* Starts the comparison of devices between Netbox and Zabbix
* Displays configuration differences and matches

### Synchronize

* Starts a one-way synchronization from Netbox to Zabbix
* Possible scenarios:
* Device exists only in Netbox → created in Zabbix
* Device exists in both → values from Netbox overwrite values in Zabbix (if they differ)
* Device is identical → nothing happens

### Webhooks
* App listens for webhook events from Netbox and synchronizes Zabbix accordingly
* /webhook_create
* /webhook_update
* /webhook_delete
