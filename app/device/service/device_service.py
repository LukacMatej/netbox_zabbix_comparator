"""_summary_
"""
import requests
import re
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as difference_model
from app.logger import logger_conf as log

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
    interfaces {
      name
      mac_address
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
            device_list.append(device_model(
              name=device["name"],
              hostgroup=device["site"]["name"]+"/"+device["device_type"]["manufacturer"]["name"]+"/"+device["role"]["name"],
              description=device["description"],
              templates=device["config_context"]["zabbix"]["templates"] if device["config_context"] else "",
              status=formatStatus(device["status"]),
              interfaces=[interface_model(
                name=interface["name"],
                mac_address=formatMac(interface["mac_address"]),
                addresses=[address_model(
                  address=ip["address"],
                  dns_name=ip["dns_name"]
                ) for ip in interface["ip_addresses"] if "address" in ip and "dns_name" in ip]
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
        "ip"
      ],
      "selectGroups": [
        "groupid",
        "name"
      ],
      "selectParentTemplates": [
        "templateid",
        "name"
      ],
      "selectInventory": [
        "macaddress_a"
      ],
    },
    "auth": key,
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
    log.logger.debug(result)
    for host in result["result"]:
      zb_device_list.append(device_model(
        name=host["name"],
        hostgroup=host["groups"][0]["name"],
        description=host["description"],
        templates=[template["name"] for template in host["parentTemplates"]],
        status=formatStatus(host["status"]),
        interfaces=[interface_model(
          name=interface["dns"],
          mac_address=formatMac(host["inventory"]["macaddress_a"]),
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
