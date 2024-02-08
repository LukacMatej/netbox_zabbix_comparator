from os import environ
# Template logic.
# Set to true to enable the template source information
# coming from config context instead of a custom field.
templates_config_context = True

# Set template and device Netbox "custom field" names
# Template_cf is not used when templates_config_context is enabled
template_cf = "zabbix_template"
device_cf = "zabbix_hostid"

# Netbox to Zabbix device state convertion
zabbix_device_removal = ["Decommissioning", "Inventory"]
zabbix_device_disable = ["Offline", "Planned", "Staged", "Failed"]

# Custom filter for device filtering. Variable must be present but can be left empty with no filtering.
# A couple of examples are as follows:

# nb_device_filter = {} #No filter
nb_device_filter = {"tag": "zabbix"} #Use a tag
# nb_device_filter = {"site": "HQ-AMS"} #Use a site name
# nb_device_filter = {"site": ["HQ-AMS", "HQ-FRA"]} #Device must be in either one of these sites
# nb_device_filter = {"site": "HQ-AMS", "tag": "zabbix", "role__n": ["PDU", "console-server"]} #Device must be in site HQ-AMS, have the tag zabbix and must not be part of the PDU or console-server role

# Default device filter, only get devices which have a name in Netbox.
# nb_device_filter = {"name__n": "null"}

#Set enviroment variables to the right netbox and zabbix informations 
environ['ZABBIX_HOST'] = "http://127.0.0.1:80"
environ['ZABBIX_TOKEN'] = "061aae75e443fba028fdaf60d76f238ddbb9c035a74bbbfce119dbc31074a26e"
environ['NETBOX_HOST'] = "http://127.0.0.1:8000"
environ['NETBOX_TOKEN'] = "dd402667fefdfc8282901ec903bef396ede5a446"