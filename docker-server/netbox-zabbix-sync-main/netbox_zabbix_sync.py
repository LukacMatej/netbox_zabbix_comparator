#!/usr/bin/python3
"""Netbox to Zabbix sync script."""
from dotenv import load_dotenv
from os import environ, path, sys
import init
import logging
import exceptions as Ex
from pynetbox import api
from pyzabbix import ZabbixAPI, ZabbixAPIException
import NetworkDevice as Nd
import ZabbixInterface
try:
    from config import *
except ModuleNotFoundError:
    print(f"Configuration file config.py not found in main directory."
           "Please create the file or rename the config.py.example file to config.py.")
    sys.exit(0)
logger = init.loggin_init(path)
load_dotenv()
def main(logger,arguments):
    """Run the sync process."""
    # set environment variables
    if(arguments.verbose):
        logger.setLevel(logging.DEBUG)
    env_vars = ["ZABBIX_HOST", "ZABBIX_USER", "ZABBIX_PASS",
                "NETBOX_HOST", "NETBOX_TOKEN"]
    for var in env_vars:
        if var not in environ:
            e = f"Environment variable {var} has not been defined."
            logger.error(e)
            raise Ex.EnvironmentVarError(e)
    # Get all virtual environment variables
    zabbix_host = environ.get("ZABBIX_HOST")
    zabbix_token = environ.get("ZABBIX_TOKEN")
    netbox_host = environ.get("NETBOX_HOST")
    netbox_token = environ.get("NETBOX_TOKEN")
    # Set Netbox API
    netbox = api(netbox_host, token=netbox_token, threading=True)
    # Check if the provided Hostgroup layout is valid
    if(arguments.layout):
        hg_objects = arguments.layout.split("/")
        allowed_objects = ["site", "manufacturer", "tenant", "dev_role"]
        # Create API call to get all custom fields which are on the device objects
        device_cfs = netbox.extras.custom_fields.filter(type="text", content_type_id=23)
        for cf in device_cfs:
            allowed_objects.append(cf.name)
        for object in hg_objects:
            if(object not in allowed_objects):
                e = (f"Hostgroup item {object} is not valid. Make sure you"
                     " use valid items and seperate them with '/'.")
                logger.error(e)
                raise Ex.HostgroupError(e)
    # Set Zabbix API
    try:
        zabbix = ZabbixAPI(zabbix_host)
        zabbix.login(api_token=zabbix_token)
    except ZabbixAPIException as e:
        e = f"Zabbix returned the following error: {str(e)}."
        logger.error(e)
    # Get all Zabbix and Netbox data
    netbox_devices = netbox.dcim.devices.filter(**nb_device_filter)
    netbox_journals = netbox.extras.journal_entries
    zabbix_groups = zabbix.hostgroup.get(output=['groupid', 'name'])
    zabbix_templates = zabbix.template.get(output=['templateid', 'name'])
    zabbix_proxys = zabbix.proxy.get(output=['proxyid', 'host'])
    # Go through all Netbox devices
    for nb_device in netbox_devices:
        try:
            device = Nd.NetworkDevice(nb_device, zabbix, netbox_journals, logger, device_cf,
                                   arguments.journal)
            device.set_hostgroup(arguments.layout, logger)
            device.set_template(templates_config_context, logger, template_cf)
            # Checks if device is part of cluster.
            # Requires the cluster argument.
            if(device.isCluster() and arguments.cluster):
                # Check if device is master or slave
                if(device.promoteMasterDevice(logger)):
                    e = (f"Device {device.name} is "
                         f"part of cluster and primary.")
                    logger.info(e)
                else:
                    # Device is secondary in cluster.
                    # Don't continue with this device.
                    e = (f"Device {device.name} is part of cluster "
                         f"but not primary. Skipping this host...")
                    logger.info(e)
                    continue
            # Checks if device is in cleanup state
            if(device.status in zabbix_device_removal):
                if(device.zabbix_id):
                    # Delete device from Zabbix
                    # and remove hostID from Netbox.
                    device.cleanup(device_cf, logger)
                    logger.info(f"Cleaned up host {device.name}.")

                else:
                    # Device has been added to Netbox
                    # but is not in Activate state
                    logger.info(f"Skipping host {device.name} since its "
                                f"not in the active state.")
                continue
            elif(device.status in zabbix_device_disable):
                device.zabbix_state = 1
            # Add hostgroup is flag is true
            # and Hostgroup is not present in Zabbix
            if(arguments.hostgroups):
                for group in zabbix_groups:
                    # If hostgroup is already present in Zabbix
                    if(group["name"] == device.hostgroup):
                        break
                else:
                    # Create new hostgroup
                    hostgroup = device.createZabbixHostgroup(logger)
                    zabbix_groups.append(hostgroup)
            # Device is already present in Zabbix
            if(device.zabbix_id):
                device.ConsistencyCheck(zabbix_groups, zabbix_templates,
                                        zabbix_proxys, arguments.proxy_power, logger)
            # Add device to Zabbix
            else:
                device.createInZabbix(zabbix_groups, zabbix_templates,
                                      zabbix_proxys, logger, device_cf)
        except Ex.SyncError:
            pass

if(__name__ == "__main__"):
    parser = init.parser_init()
    args = parser.parse_args()
    main(logger,args)
