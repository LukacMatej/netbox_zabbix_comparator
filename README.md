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
  -e PROXY_ROOT_PATH=<dev|prod> \
  -e ZABBIX_AGENT_PORT=<Zabbix Agent interface port, default 10050> \
  -e ZABBIX_SNMP_PORT=<Zabbix SNMP interface port, default 161> \
  -e ZABBIX_IPMI_PORT=<Zabbix IPMI interface port, default 623> \
  -e ZABBIX_JMX_PORT=<Zabbix JMX interface port, default 12345> \
  -e SNMPV2_MACRO=<SNMPv2 community string or Zabbix macro, default {$SNMP_COMMUNITY}> \
  -e ZABBIX_SNMPV3_SECURITY_NAME=<SNMPv3 security name> \
  -e ZABBIX_SNMPV3_SECURITY_LEVEL=<SNMPv3 security level: 0=noAuthNoPriv, 1=authNoPriv, 2=authPriv, default 2> \
  -e ZABBIX_SNMPV3_AUTH_PROTOCOL=<SNMPv3 auth protocol code, default 1 (SHA1)> \
  -e ZABBIX_SNMPV3_AUTH_PASSPHRASE=<SNMPv3 auth passphrase> \
  -e ZABBIX_SNMPV3_PRIV_PROTOCOL=<SNMPv3 priv protocol code, default 1 (AES128)> \
  -e ZABBIX_SNMPV3_PRIV_PASSPHRASE=<SNMPv3 priv passphrase> \
  -e ZABBIX_SNMPV3_CONTEXT_NAME=<SNMPv3 context name>
  netbox-zabbix

```

## Setup for Proper Application Operation

### Priority for Selecting Templates, Port Types and Host Groups

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
* A Netbox script is available to synchronize Custom Field Choices named `zabbix_templates` with templates in Zabbix. For a similar guide, see Zabbix hostgroups.

### Port Type

* Specifies the port type for communication with Zabbix
* Supported types: Agent, SNMPv2, SNMPv3, JMX, IPMI
* Plain `SNMP` is no longer a valid choice — update the `zabbix_port_type` Custom Field Choices in NetBox to `SNMPv2`/`SNMPv3` instead. A device/role still configured with the old `SNMP` value is treated as if no port type were set until it's updated.

### Primary IP Address

* A mandatory setting in Netbox for proper operation
* Used as the connection address for the device in Zabbix
* Selected from `primary_ip4` on the device

### Zabbix Host Groups

A Netbox script is available to synchronize Custom Field Choices named `zabbix_hostgroups` with host groups in Zabbix:

* Link Custom Field Choices to a Custom Field named `zabbix_hostgroups`
* Set it as multi-select on DCIM > DEVICE and DCIM > DEVICE ROLE (role values are used when the device has none, see the priority above)
* The default host group in Zabbix is set to "Netbox" to keep track of all devices created by the synchronization

### Excluded Hostgroups

* `EXCLUDED_HOSTGROUPS` optionally names a single Zabbix hostgroup to exclude from comparison
* Zabbix hosts belonging to that hostgroup are dropped from the comparison results entirely (they are neither shown as "Zabbix-only", nor matched against NetBox, nor synchronized)
* This is unrelated to `ZABBIX_DEFAULT_HOSTGROUP`, which only controls which hostgroup a newly-created Zabbix host is assigned to
* Leave unset (or empty) to include all hosts

### Zabbix Interface Ports

* `ZABBIX_AGENT_PORT`, `ZABBIX_SNMP_PORT`, `ZABBIX_IPMI_PORT`, `ZABBIX_JMX_PORT` set the port used when creating/updating the corresponding Zabbix interface type
* `ZABBIX_SNMP_PORT` is shared by both SNMPv2 and SNMPv3 — Zabbix has one port per interface type, not per SNMP version
* Default to Zabbix's own defaults (10050, 161, 623, 12345) if unset

### SNMPv2/SNMPv3 Configuration

Since `SNMPv2`/`SNMPv3` are deployment-wide credentials (not per-device), they're read from environment variables rather than NetBox:

* `SNMPV2_MACRO` — the community string (or Zabbix user macro, e.g. `{$SNMP_COMMUNITY}`) used for SNMPv2 interfaces. Defaults to `{$SNMP_COMMUNITY}` if unset.
* `ZABBIX_SNMPV3_SECURITY_NAME` — SNMPv3 security name
* `ZABBIX_SNMPV3_SECURITY_LEVEL` — SNMPv3 security level: `0`=noAuthNoPriv, `1`=authNoPriv, `2`=authPriv (default `2`)
* `ZABBIX_SNMPV3_AUTH_PROTOCOL` — SNMPv3 auth protocol, Zabbix's numeric code (default `1` = SHA1)
* `ZABBIX_SNMPV3_AUTH_PASSPHRASE` — SNMPv3 auth passphrase
* `ZABBIX_SNMPV3_PRIV_PROTOCOL` — SNMPv3 priv protocol, Zabbix's numeric code (default `1` = AES128)
* `ZABBIX_SNMPV3_PRIV_PASSPHRASE` — SNMPv3 priv passphrase
* `ZABBIX_SNMPV3_CONTEXT_NAME` — SNMPv3 context name (optional)

See Zabbix's API documentation for the full list of `authprotocol`/`privprotocol` numeric codes.

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
