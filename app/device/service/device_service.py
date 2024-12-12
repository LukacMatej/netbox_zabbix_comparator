"""_summary_
"""
import requests
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model


def print_devices(nb_device_list: list[device_model]) -> None:
  for device in nb_device_list:
    print(f"Device Name: {device.name}")
    print(f"Description: {device.description}")
    print(f"Status: {device.status}")
    print(f"Templates: {device.templates}")
    for interface in device.interfaces:
      print(f"  Interface Name: {interface.name}")
      print(f"  MAC Address: {interface.mac_address}")
      for address in interface.addresses:
        print(f"    IP Address: {address.address}")
        print(f"    DNS Name: {address.dns_name}")

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
      if response.status_code == 200:
          data = response.json()
          for device in data["data"]["device_list"]:
            device_list.append(device_model(
              name=device["name"],
              hostgroup="",
              description=device["description"],
              templates=device["config_context"]["zabbix"]["templates"] if device["config_context"] else "",
              status=device["status"],
              interfaces=[interface_model(
                name=interface["name"],
                mac_address=interface["mac_address"],
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
  key = "14a116237840d411e877d16b511eecc00818a3c050470648db9a91d2326e00f5"
  ip = "localhost"
  ip = f"http://{ip}/api_jsonrpc.php"
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
    response = requests.post(ip, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()
    for host in result["result"]:
      zb_device_list.append(device_model(
        name=host["name"],
        hostgroup=host["groups"][0]["name"],
        description=host["description"],
        templates=[template["name"] for template in host["parentTemplates"]],
        status=host["status"],
        interfaces=[interface_model(
          name=interface["dns"],
          mac_address=host["inventory"]["macaddress_a"],
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

# get_zb_devices("","")