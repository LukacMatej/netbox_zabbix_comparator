import exceptions as Ex
import ZabbixInterface as ZI
class NetworkDevice():
    """
    Represents Network device.
    INPUT: (Netbox device class, ZabbixAPI class, journal flag, NB journal class)
    """

    def __init__(self, nb, zabbix, nb_journal_class, logger, device_cf, journal=None):
        self.nb = nb
        self.id = nb.id
        self.name = nb.name if nb.primary_ip.dns_name == "None" or nb.primary_ip.dns_name == "" else nb.primary_ip.dns_name
        self.status = nb.status.label
        self.zabbix = zabbix
        self.tenant = nb.tenant
        self.config_context = nb.config_context
        self.hostgroup = ""
        self.zbxproxy = "0"
        self.zabbix_state = 0
        self.journal = journal
        self.nb_journals = nb_journal_class
        self._setBasics(logger,device_cf)

    def _setBasics(self,logger,device_cf):
        """
        Sets basic information like IP address.
        """
        # Return error if device does not have primary IP.
        if(self.nb.primary_ip):
            self.cidr = self.nb.primary_ip.address
            self.ip = self.cidr.split("/")[0]
        else:
            e = f"Device {self.name}: no primary IP."
            logger.warning(e)
            raise Ex.SyncInventoryError(e)

        # Check if device has custom field for ZBX ID
        if(device_cf in self.nb.custom_fields):
            self.zabbix_id = self.nb.custom_fields[device_cf]
        else:
            e = f"Custom field {device_cf} not found for {self.name}."
            logger.warning(e)
            raise Ex.SyncInventoryError(e)

    def set_hostgroup(self, format, logger):
        """Set the hostgroup for this device"""
        # Get all variables from the NB data
        site = self.nb.site.name
        manufacturer = self.nb.device_type.manufacturer.name
        role = self.nb.device_role.name
        tenant = self.tenant.name if self.tenant else None

        hostgroup_vars = {"site": site, "manufacturer": manufacturer,
                          "dev_role": role, "tenant": tenant}
        items = format.split("/")
        # Go through all hostgroup items
        for item in items:
            # Check if this item is not the first in the hostgroup format
            if(self.hostgroup):
                self.hostgroup += "/"
            # Check if the item is not a standard item, A.K.A. custom field name
            if(item not in hostgroup_vars):
                # check if the item is in the custom fields
                if(item in self.nb.custom_fields):
                    cf_value = self.nb.custom_fields[item]
                    # check if the CF is empty.
                    if(not cf_value):
                        # Remove the previously inserted /
                        self.hostgroup = self.hostgroup[:-1]
                        continue
                    else:
                        self.hostgroup += cf_value
                        continue
                else:
                    continue
            # Check if the variable (such as Tenant) is empty
            if(not hostgroup_vars[item]):
                continue
            # Add the item to the hostgroup format
            self.hostgroup += hostgroup_vars[item]
        if(not self.hostgroup):
            e = (f"{self.name} has no reliable hostgroup. This is"
                 "most likely due to the use of custom fields that are empty.")
            logger.error(e)
            raise Ex.SyncInventoryError(e)
    
    def set_template(self, templates_config_context,logger,template_cf):
        if templates_config_context:
            # Template lookup using config context
            if("zabbix" not in self.config_context):
                e = ("Key 'zabbix' not found in config "
                     f"context for template host {self.name}")
                logger.warning(e)
                raise Ex.SyncInventoryError(e)
            if("templates" not in self.config_context["zabbix"]):
                e = ("Key 'zabbix' not found in config "
                     f"context for template host {self.name}")
                logger.warning(e)
                raise Ex.SyncInventoryError(e)
            self.zbx_template_names = self.config_context["zabbix"]["templates"]
        else:
            # Get device type custom fields
            device_type_cfs = self.nb.device_type.custom_fields
            # Check if the ZBX Template CF is present
            if(template_cf in device_type_cfs):
                # Set value to template
                self.zbx_template_names = [device_type_cfs[template_cf]]
            else:
                # Custom field not found, return error
                e = (f"Custom field {template_cf} not "
                    f"found for {self.nb.device_type.manufacturer.name}"
                    f" - {self.nb.device_type.display}.")
                logger.warning(e)
                raise Ex.SyncInventoryError(e)

    def isCluster(self):
        """
        Checks if device is part of cluster.
        """
        if(self.nb.virtual_chassis):
            return True
        else:
            return False

    def getClusterMaster(self,logger):
        """
        Returns chassis master ID.
        """
        if(not self.isCluster()):
            e = (f"Unable to proces {self.name} for cluster calculation: "
                 f"not part of a cluster.")
            logger.warning(e)
            raise Ex.SyncInventoryError(e)
        elif(not self.nb.virtual_chassis.master):
            e = (f"{self.name} is part of a Netbox virtual chassis which does "
                 "not have a master configured. Skipping for this reason.")
            logger.error(e)
            raise Ex.SyncInventoryError(e)
        else:
            return self.nb.virtual_chassis.master.id

    def promoteMasterDevice(self,logger):
        """
        If device is Primary in cluster,
        promote device name to the cluster name.
        Returns True if succesfull, returns False if device is secondary.
        """
        masterid = self.getClusterMaster()
        if(masterid == self.id):
            logger.debug(f"Device {self.name} is primary cluster member. "
                         f"Modifying hostname from {self.name} to " +
                         f"{self.nb.virtual_chassis.name}.")
            self.name = self.nb.virtual_chassis.name

            return True
        else:
            logger.debug(f"Device {self.name} is non-primary cluster member.")
            return False

    def zbxTemplatePrepper(self, templates,logger):
        """
        Returns Zabbix template IDs
        INPUT: list of templates from Zabbix
        OUTPUT: True
        """
        # Check if there are templates defined
        if(not self.zbx_template_names):
            e = (f"Device template '{self.nb.device_type.display}' "
                 "has no Zabbix templates defined.")
            logger.info(e)
            raise Ex.SyncInventoryError()
        # Set variable to empty list
        self.zbx_templates = []
        # Go through all templates definded in Netbox
        for nb_template in self.zbx_template_names:
            template_match = False
            # Go through all templates found in Zabbix
            for zbx_template in templates:
                # If the template names match
                if(zbx_template['name'] == nb_template):
                    # Set match variable to true, add template details
                    # to class variable and return debug log
                    template_match = True
                    self.zbx_templates.append({"templateid": zbx_template['templateid'],
                                               "name": zbx_template['name']}) 
                    e = (f"Found template {zbx_template['name']}"
                        f" for host {self.name}.")
                    logger.debug(e)
            # Return error should the template not be found in Zabbix
            if(not template_match):
                e = (f"Unable to find template {nb_template} "
                    f"for host {self.name} in Zabbix. Skipping host...")
                logger.warning(e)
                raise Ex.SyncInventoryError(e)

    def getZabbixGroup(self, groups, logger):
        """
        Returns Zabbix group ID
        INPUT: list of hostgroups
        OUTPUT: True / False
        """
        # Go through all groups
        for group in groups:
            if(group['name'] == self.hostgroup):
                self.group_id = group['groupid']
                e = (f"Found group {group['name']} for host {self.name}.")
                logger.debug(e)
                return True
        else:
            e = (f"Unable to find group '{self.hostgroup}' "
                 f"for host {self.name} in Zabbix.")
            logger.warning(e)
            raise Ex.SyncInventoryError(e)

    def cleanup(self, device_cf, logger):
        """
        Removes device from external resources.
        Resets custom fields in Netbox.
        """
        if(self.zabbix_id):
            try:
                self.zabbix.host.delete(self.zabbix_id)
                self.nb.custom_fields[device_cf] = None
                self.nb.save()
                e = f"Deleted host {self.name} from Zabbix."
                logger.info(e)
                self.create_journal_entry("warning", "Deleted host from Zabbix", logger)
            except Ex.ZabbixAPIException as e:
                e = f"Zabbix returned the following error: {str(e)}."
                logger.error(e)
                raise Ex.SyncExternalError(e)

    def _zabbixHostnameExists(self):
        """
        Checks if hostname exists in Zabbix.
        """
        host = self.zabbix.host.get(filter={'name': self.name}, output=[])
        if(host):
            return True
        else:
            return False

    def setInterfaceDetails(self, logger):
        """
        Checks interface parameters from Netbox and
        creates a model for the interface to be used in Zabbix.
        """
        try:
            # Initiate interface class
            interface = ZI.ZabbixInterface(self.nb.config_context, self.ip)
            # Check if Netbox has device context.
            # If not fall back to old config.
            if(interface.get_context()):
                # If device is SNMP type, add aditional information.
                if(interface.interface["type"] == 2):
                    interface.set_snmp()
            else:
                interface.set_default()
            return [interface.interface]
        except Ex.InterfaceConfigError as e:
            e = f"{self.name}: {e}"
            logger.warning(e)
            raise Ex.SyncInventoryError(e)

    def setProxy(self, proxy_list, logger):
        # check if Zabbix Proxy has been defined in config context
        if("zabbix" in self.nb.config_context):
            if("proxy" in self.nb.config_context["zabbix"]):
                proxy = self.nb.config_context["zabbix"]["proxy"]
                # Try matching proxy
                for px in proxy_list:
                    if(px["host"] == proxy):
                        self.zbxproxy = px["proxyid"]
                        logger.debug(f"Found proxy {proxy}"
                                     f" for {self.name}.")
                        return True
                else:
                    e = f"{self.name}: Defined proxy {proxy} not found."
                    logger.warning(e)
                    return False

    def createInZabbix(self, groups, templates, proxys, logger, device_cf,
                       description="Host added by Netbox sync script."):
        """
        Creates Zabbix host object with parameters from Netbox object.
        """
        # Check if hostname is already present in Zabbix
        if(not self._zabbixHostnameExists()):
            # Get group and template ID's for host
            if(not self.getZabbixGroup(groups, logger)):
                raise Ex.SyncInventoryError()
            self.zbxTemplatePrepper(templates, logger)
            # Set interface, group and template configuration
            interfaces = self.setInterfaceDetails(logger)
            groups = [{"groupid": self.group_id}]
            # Set Zabbix proxy if defined
            self.setProxy(proxys, logger)
            # Add host to Zabbix
            try:
                host = self.zabbix.host.create(host=self.name,
                                               status=self.zabbix_state,
                                               interfaces=interfaces,
                                               groups=groups,
                                               templates=self.zbx_templates,
                                               proxy_hostid=self.zbxproxy,
                                               description=description)
                self.zabbix_id = host["hostids"][0]
            except Ex.ZabbixAPIException as e:
                e = f"Couldn't add {self.name}, Zabbix returned {str(e)}."
                logger.error(e)
                raise Ex.SyncExternalError(e)
            # Set Netbox custom field to hostID value.
            self.nb.custom_fields[device_cf] = int(self.zabbix_id)
            self.nb.save()
            msg = f"Created host {self.name} in Zabbix."
            logger.info(msg)
            self.create_journal_entry("success", msg, logger)
        else:
            e = f"Unable to add {self.name} to Zabbix: host already present."
            logger.warning(e)

    def createZabbixHostgroup(self, logger):
        """
        Creates Zabbix host group based on hostgroup format.
        """
        try:
            groupid = self.zabbix.hostgroup.create(name=self.hostgroup)
            e = f"Added hostgroup '{self.hostgroup}'."
            logger.info(e)
            data = {'groupid': groupid["groupids"][0], 'name': self.hostgroup}
            return data
        except Ex.ZabbixAPIException as e:
            e = f"Couldn't add hostgroup, Zabbix returned {str(e)}."
            logger.error(e)
            raise Ex.SyncExternalError(e)

    def updateZabbixHost(self, logger, **kwargs):
        """
        Updates Zabbix host with given parameters.
        INPUT: Key word arguments for Zabbix host object.
        """
        try:
            self.zabbix.host.update(hostid=self.zabbix_id, **kwargs)
        except Ex.ZabbixAPIException as e:
            e = f"Zabbix returned the following error: {str(e)}."
            logger.error(e)
            raise Ex.SyncExternalError(e)
        logger.info(f"Updated host {self.name} with data {kwargs}.")
        self.create_journal_entry("info", f"Updated host in Zabbix with latest NB data.", logger)

    def ConsistencyCheck(self, groups, templates, proxys, proxy_power, logger):
        """
        Checks if Zabbix object is still valid with Netbox parameters.
        """
        self.getZabbixGroup(groups, logger)
        self.zbxTemplatePrepper(templates, logger)
        self.setProxy(proxys, logger)
        host = self.zabbix.host.get(filter={'hostid': self.zabbix_id},
                                    selectInterfaces=['type', 'ip',
                                                      'port', 'details',
                                                      'interfaceid'],
                                    selectGroups=["groupid"],
                                    selectParentTemplates=["templateid"])
        if(len(host) > 1):
            e = (f"Got {len(host)} results for Zabbix hosts "
                 f"with ID {self.zabbix_id} - hostname {self.name}.")
            logger.error(e)
            raise Ex.SyncInventoryError(e)
        elif(len(host) == 0):
            e = (f"No Zabbix host found for {self.name}. "
                 f"This is likely the result of a deleted Zabbix host "
                 f"without zeroing the ID field in Netbox.")
            logger.error(e)
            raise Ex.SyncInventoryError(e)
        else:
            host = host[0]

        if(host["host"] == self.name):
            logger.debug(f"Device {self.name}: hostname in-sync.")
        else:
            logger.warning(f"Device {self.name}: hostname OUT of sync. "
                           f"Received value: {host['host']}")
            self.updateZabbixHost(logger, host=self.name)
        
        # Check if the templates are in-sync
        if(not self.zbx_template_comparer(host["parentTemplates"], logger)):
            logger.warning(f"Device {self.name}: template(s) OUT of sync.")
            # Update Zabbix with NB templates and clear any old / lost templates
            self.updateZabbixHost(logger, templates_clear=host["parentTemplates"], templates=self.zbx_templates)
        else:
            logger.debug(f"Device {self.name}: template(s) in-sync.")

        for group in host["groups"]:
            if(group["groupid"] == self.group_id):
                logger.debug(f"Device {self.name}: hostgroup in-sync.")
                break
        else:
            logger.warning(f"Device {self.name}: hostgroup OUT of sync.")
            self.updateZabbixHost(logger, groups={'groupid': self.group_id})

        if(int(host["status"]) == self.zabbix_state):
            logger.debug(f"Device {self.name}: status in-sync.")
        else:
            logger.warning(f"Device {self.name}: status OUT of sync.")
            self.updateZabbixHost(logger, status=str(self.zabbix_state))

        # Check if a proxy has been defined
        if(self.zbxproxy != "0"):
            # Check if expected proxyID matches with configured proxy
            if(host["proxy_hostid"] == self.zbxproxy):
                logger.debug(f"Device {self.name}: proxy in-sync.")
            else:
                # Proxy diff, update value
                logger.warning(f"Device {self.name}: proxy OUT of sync.")
                self.updateZabbixHost(logger, proxy_hostid=self.zbxproxy)
        else:
            if(not host["proxy_hostid"] == "0"):
                if(proxy_power):
                    # If the -p flag has been issued,
                    # delete the proxy link in Zabbix
                    self.updateZabbixHost(logger, proxy_hostid=self.zbxproxy)
                else:
                    # Instead of deleting the proxy config in zabbix and
                    # forcing potential data loss,
                    # an error message is displayed.
                    logger.error(f"Device {self.name} is configured "
                                 f"with proxy in Zabbix but not in Netbox. The"
                                 " -p flag was ommited: no "
                                 "changes have been made.")
        # If only 1 interface has been found
        if(len(host['interfaces']) == 1):
            updates = {}
            # Go through each key / item and check if it matches Zabbix
            for key, item in self.setInterfaceDetails(logger)[0].items():
                # Check if Netbox value is found in Zabbix
                if(key in host["interfaces"][0]):
                    # If SNMP is used, go through nested dict
                    # to compare SNMP parameters
                    if(type(item) == dict and key == "details"):
                        for k, i in item.items():
                            if(k in host["interfaces"][0][key]):
                                # Set update if values don't match
                                if(host["interfaces"][0][key][k] != str(i)):
                                    # If dict has not been created, add it
                                    if(key not in updates):
                                        updates[key] = {}
                                    updates[key][k] = str(i)
                                    # If SNMP version has been changed
                                    # break loop and force full SNMP update
                                    if(k == "version"):
                                        break
                        # Force full SNMP config update
                        # when version has changed.
                        if(key in updates):
                            if("version" in updates[key]):
                                for k, i in item.items():
                                    updates[key][k] = str(i)
                        continue
                    # Set update if values don't match
                    if(host["interfaces"][0][key] != str(item)):
                        updates[key] = item
            if(updates):
                # If interface updates have been found: push to Zabbix
                logger.warning(f"Device {self.name}: Interface OUT of sync.")
                if("type" in updates):
                    # Changing interface type not supported. Raise exception.
                    e = (f"Device {self.name}: changing interface type to "
                         f"{str(updates['type'])} is not supported.")
                    logger.error(e)
                    raise Ex.InterfaceConfigError(e)
                # Set interfaceID for Zabbix config
                updates["interfaceid"] = host["interfaces"][0]['interfaceid']
                try:
                    # API call to Zabbix
                    self.zabbix.hostinterface.update(updates)
                    e = f"Solved {self.name} interface conflict."
                    logger.info(e)
                    self.create_journal_entry("info", e, logger)
                except Ex.ZabbixAPIException as e:
                    e = f"Zabbix returned the following error: {str(e)}."
                    logger.error(e)
                    raise Ex.SyncExternalError(e)
            else:
                # If no updates are found, Zabbix interface is in-sync
                e = f"Device {self.name}: interface in-sync."
                logger.debug(e)
        else:
            e = (f"Device {self.name} has unsupported interface configuration."
                 f" Host has total of {len(host['interfaces'])} interfaces. "
                 "Manual interfention required.")
            logger.error(e)
            Ex.SyncInventoryError(e)

    def create_journal_entry(self, severity, message, logger):
        # Send a new Journal entry to Netbox. Usefull for viewing actions
        # in Netbox without having to look in Zabbix or the script log output
        if(self.journal):
            # Check if the severity is valid
            if severity not in ["info", "success", "warning", "danger"]:
                logger.warning(f"Value {severity} not valid for NB journal entries.")
                return False
            journal = {"assigned_object_type": "dcim.device",
                       "assigned_object_id": self.id,
                       "kind": severity,
                       "comments": message
                       }
            try:
                self.nb_journals.create(journal)
                return True
                logger.debug(f"Crated journal entry in NB for host {self.name}")
            except Ex.pynetbox.RequestError as e:
                logger.warning("Unable to create journal entry for "
                               f"{self.name}: NB returned {e}")
    
    def zbx_template_comparer(self, tmpls_from_zabbix ,logger):
        """
        Compares the Netbox and Zabbix templates with each other.
        Should there be a mismatch then the function will return false

        INPUT: list of NB and ZBX templates
        OUTPUT: Boolean True/False
        """
        succesfull_templates = []
        # Go through each Netbox template
        for nb_tmpl in self.zbx_templates:
            # Go through each Zabbix template
            for pos, zbx_tmpl in enumerate(tmpls_from_zabbix):
                # Check if template IDs match
                if(nb_tmpl["templateid"] == zbx_tmpl["templateid"]):
                    # Templates match. Remove this template from the Zabbix templates
                    # and add this NB template to the list of successfull templates
                    tmpls_from_zabbix.pop(pos)
                    succesfull_templates.append(nb_tmpl)
                    logger.debug(f"Device {self.name}: template {nb_tmpl['name']} is present in Zabbix.")
                    break
        if(len(succesfull_templates) == len(self.zbx_templates) and
           len(tmpls_from_zabbix) == 0):
            # All of the Netbox templates have been confirmed as successfull
            # and the ZBX template list is empty. This means that
            # all of the templates match.
            return True
        return False
