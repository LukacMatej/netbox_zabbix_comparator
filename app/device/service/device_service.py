"""_summary_
"""
import requests
import re
import os
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as difference_model
from app.logger import logger_conf as log

def find_hostinterface_id(hostid: str) -> int:
  """
  Finds the interface ID for a given Zabbix host ID and interface name.
  Args:
    hostid (str): The Zabbix host ID.
    interface_name (str): The name (DNS or IP) of the interface to find.
  Returns:
    int: The interface ID if found, otherwise -1.
  """
  zb_url = os.environ.get("ZABBIX_IP")
  zb_key = os.environ.get("ZABBIX_KEY")
  headers = {
    "Authorization": f"Bearer {zb_key}",
    "Content-Type": "application/json-rpc",
  }
  payload = {
    "jsonrpc": "2.0",
    "method": "hostinterface.get",
    "params": {
      "hostids": hostid,
      "output": ["interfaceid"]
    },
    "id": 1
  }
  try:
    response = requests.post(f"{zb_url}/api_jsonrpc.php", headers=headers, json=payload)
    response.raise_for_status()
    log.logger.debug(f"Response from Zabbix API: {response.json()}")
    result = response.json()
    if "error" in result:
      log.logger.error(f"Error in Zabbix API response: {result['error']}")
      return -1
    interface = result.get("result", [])
    return int(interface[0]["interfaceid"]) if interface else -1
  except Exception as e:
    log.logger.error(f"Failed to find Zabbix interface ID for hostid {hostid}: {e}")
  return -1

def find_nb_site_id(site_name: str) -> int:
    """Finds the Netbox site ID based on the provided site name.
    Args:
        site_name (str): The name of the site to find.
    Returns:
        int: The ID of the site if found, otherwise -1.
    """
    log.logger.info(f"Finding Netbox site ID for {site_name}.")
    nb_ip = os.environ.get("NETBOX_IP")
    nb_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {nb_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    response = requests.get(f"{nb_ip}/api/dcim/sites/?name={site_name}", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["count"] > 0:
            site_id = data["results"][0]["id"]
            log.logger.info(f"Found Netbox site ID: {site_id} for {site_name}.")
            return int(site_id)
    
    log.logger.error(f"Failed to find Netbox site ID for {site_name}: {response.text}")
    return -1

def find_nb_device_type_id(device_type: str) -> int:
    """Finds the Netbox device type ID based on the provided device type.
    Args:
        device_type (str): The name of the device type to find.
    Returns:
        int: The ID of the device type if found, otherwise -1.
    """
    log.logger.info(f"Finding Netbox device type ID for {device_type}.")
    nb_ip = os.environ.get("NETBOX_IP")
    nb_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {nb_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    response = requests.get(f"{nb_ip}/api/dcim/device-types/?model={device_type}", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["count"] > 0:
            device_type_id = data["results"][0]["id"]
            log.logger.info(f"Found Netbox device type ID: {device_type_id} for {device_type}.")
            return int(device_type_id)
    
    log.logger.error(f"Failed to find Netbox device type ID for {device_type}: {response.text}")
    return -1

def find_nb_device_role_id(device_role: str) -> int:
    """Finds the Netbox device role ID based on the provided device role.
    Args:
        device_role (str): The name of the device role to find.
    Returns:
        int: The ID of the device role if found, otherwise -1.
    """
    log.logger.info(f"Finding Netbox device role ID for {device_role}.")
    nb_ip = os.environ.get("NETBOX_IP")
    nb_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {nb_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    response = requests.get(f"{nb_ip}/api/dcim/device-roles/?name={device_role}", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["count"] > 0:
            device_role_id = data["results"][0]["id"]
            log.logger.info(f"Found Netbox device role ID: {device_role_id} for {device_role}.")
            return int(device_role_id)
    
    log.logger.error(f"Failed to find Netbox device role ID for {device_role}: {response.text}")
    return -1

def format_address(address: str) -> str:
  if "/" in address:
    return address.split("/")[0]
  return address

def formatStatus(status: str)-> str:
  enabled_statuses = {"ACTIVE",0}
  disabled_statuses = {"OFFLINE","STAGED","PLANNED","FAILED","INVENTORY"}
  if status in enabled_statuses:
    return "Active"
  elif status in disabled_statuses:
    return "Disabled"
  return status

def formatMac(mac: str) -> str:
    if not mac:
      return ""
    mac_clean = re.sub(r'[^0-9A-Fa-f]', '', mac)
    return f"{mac_clean[0:4]}.{mac_clean[4:8]}.{mac_clean[8:12]}".lower()

def print_differences(difference_model: list[difference_model]) -> str:
    txt_builder: str = ""
    for differ in difference_model:
      txt_builder += f"Netbox device: {print_device(differ.nb_device)}\n"
      txt_builder += f"Zabbix device: {print_device(differ.zb_device)}\n"
      txt_builder += "Differences:\n"
      for difference in differ.differences[0]:
          txt_builder += f"  {difference}\n"
      txt_builder += "Similarities:\n"
      for similarity in differ.differences[1]:
          txt_builder += f"  {similarity}\n"
    return txt_builder

def print_devices(nb_device_list: list[device_model]) -> str:
  txt_builder: str = ""
  for device in nb_device_list:
    txt_builder += f"Device Name: {device.name}\n"
    txt_builder += f"Description: {device.description}\n"
    txt_builder += f"Status: {device.status}\n"
    txt_builder += f"Hostgroup: {device.hostgroup}\n"
    txt_builder += f"Templates: {device.templates}\n"
    for interface in device.interfaces:
      txt_builder += f"  Interface Name: {interface.name}\n"
      txt_builder += f"  MAC Address: {interface.mac_address}\n"
      txt_builder += f"  Port Type: {interface.port_type}\n"
      for address in interface.addresses:
        txt_builder += f"    IP Address: {address.address}\n"
        txt_builder += f"    DNS Name: {address.dns_name}\n"
  return txt_builder

def print_device(device: device_model) -> str:
  txt_builder: str = ""
  txt_builder += f"Device Name: {device.name}\n"
  txt_builder += f"Description: {device.description}\n"
  txt_builder += f"Status: {device.status}\n"
  txt_builder += f"Hostgroup: {device.hostgroup}\n"
  txt_builder += f"Templates: {device.templates}\n"
  for interface in device.interfaces:
    txt_builder += f"  Interface Name: {interface.name}\n"
    txt_builder += f"  MAC Address: {interface.mac_address}\n"
    txt_builder += f"  Port Type: {returnPortTypeName(interface.port_type)}\n"
    for address in interface.addresses:
      txt_builder += f"    IP Address: {address.address}\n"
      txt_builder += f"    DNS Name: {address.dns_name}\n"
  return txt_builder

def get_nb_devices(key: str, ip: str) -> list[device_model] | str:
  headers: dict[str, str] = {
      "Authorization": f"Token {key}",
      "Content-Type": "application/json",
      "Accept": "application/json" 
  }
  query = """
  {
  device_list {
    id
    name
    site {
      name
    }
    device_type {
      manufacturer {
        name
      }
    }
    role {
      name
    }
    config_context
    status
    description
    primary_ip4 {
      address
      dns_name
    }
    interfaces {
      name
      mac_addresses {
        mac_address
      }
      ip_addresses {
        address
        dns_name
      }
    }
  }
}
  """
  
  try:
      response: requests.Response = requests.get(
          ip,
          headers=headers,
          json={"query": query}
      )
      device_list: list[device_model] = []
      log.logger.debug(response)
      if response.status_code == 200:
          data = response.json()
          for device in data["data"]["device_list"]:
            if device["config_context"] and "zabbix" in device["config_context"] and "templates" in device["config_context"]["zabbix"] and "port_type" in device["config_context"]["zabbix"]:
              device_list.append(device_model(
                name=device["name"],
                hostgroup="Netbox synchronized devices",
                description=device["description"],
                templates=device["config_context"]["zabbix"]["templates"] if device["config_context"] else "",
                status=formatStatus(device["status"]),
                interfaces=[interface_model(
                  name=interface["name"],
                  mac_address=formatMac(interface["mac_addresses"][0]["mac_address"]) if interface["mac_addresses"] else "",
                  port_type=device["config_context"]["zabbix"]["port_type"] if device["config_context"] else "",
                  addresses=[address_model(
                    address=str(device["primary_ip4"]["address"]).split("/")[0] if device["primary_ip4"] else "",
                    dns_name=device["primary_ip4"]["dns_name"] if device["primary_ip4"] else ""
                  )]
                ) for interface in device["interfaces"] if interface["ip_addresses"]]
              ))
      return device_list
  except requests.exceptions.RequestException as e:
      return (f"Request failed: {e}")

def get_zb_devices(key: str, ip: str) -> list[device_model] | str:
  ip = f"{ip}/api_jsonrpc.php"
  payload = {
    "jsonrpc": "2.0",
    "method": "host.get",
    "params": {
      "output": ["hostid","host","name","status","description"],
      "selectInterfaces": [
        "interfaceid",
        "dns",
        "ip",
        "type"
      ],
      "selectGroups": [
        "groupid",
        "name"
      ],
      "selectParentTemplates": [
        "templateid",
        "name"
      ],
      "filter": {
        "status": [0]
      }
    },
    "id": 1
  }
  headers: dict[str, str] = {
    "Authorization": f"Bearer {key}",
    'Content-Type': 'application/json-rpc',
    'Accept': 'application/json',
  }
  try:
    zb_device_list: list[device_model] = []
    response: requests.Response = requests.post(ip, headers=headers, json=payload)
    log.logger.debug(response)
    response.raise_for_status()
    result = response.json()
    if "error" in result:
      log.logger.error(f"Error in Zabbix API response: {result['error']}")
      return f"Error in Zabbix API response: {result['error']}"
    log.logger.debug(result)
    for host in result["result"]:
      zb_device_list.append(device_model(
        name=host["name"],
        hostgroup=host["groups"],
        description=host["description"],
        templates=[template["name"] for template in host["parentTemplates"]],
        status=formatStatus(host["status"]),
        interfaces=[interface_model(
          name=interface["dns"],
          mac_address="",
          port_type=interface["type"],
          addresses=[address_model(
            address=interface["ip"],
            dns_name=interface["dns"]
          )
          ]
        ) for interface in host["interfaces"]]
      ))
  except requests.exceptions.RequestException as e:
    return (f"Request failed: {e}")
  return zb_device_list

def formatPortType(port_type: str) -> str:
    """Maps the port type to a Netbox compatible format."""
    if isinstance(port_type, list):
        port_type = port_type[0] if port_type else ""
    port_type_map: dict[str, str] = {
        "Agent": "1",
        "SNMP": "2",
        "IPMI": "3",
        "JMX": "4",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4"
    }
    return port_type_map.get(port_type, "1")
  
def returnPortTypeName(port_type: str) -> str:
    """Returns the name of the port type based on its identifier."""
    port_type_name_map: dict[str, str] = {
        "1": "Agent",
        "2": "SNMP",
        "3": "IPMI",
        "4": "JMX"
    }
    return port_type_name_map.get(port_type, "Agent")
  