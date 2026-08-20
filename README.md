# Netbox and Zabbix Device Comparison and Synchronization

The application is used to synchronize device configurations between Netbox and Zabbix, featuring the ability to compare and automatically create/update devices in Zabbix based on the configuration in Netbox.

## Running Docker

```bash
docker run -d \
  -p <port>:<port> \
  -e LISTEN_ADDRESS=<IP address> \
  -e HTTP_PORT=<port> \
  -e ZABBIX_DEFAULT_HOSTGROUP=<default hostgroup name> \
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

### Custom Validation

Zabbix has many dependencies regarding the Port Type - Templates relationship. For this reason, a custom validation config was created to communicate with Zabbix and handle these dependencies.

* The custom validator calls the endpoint only when editing custom fields for Zabbix, see above.

##### Procedure:

* Place `device_zabbix_validator.py` into the Netbox root folder
* Insert the following into `configuration/extra.py`:
```python
CUSTOM_VALIDATORS = {
    'dcim.device': (
        'device_zabbix_validator.ZabbixCustomFieldValidator',
    )
}

```



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
