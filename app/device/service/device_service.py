"""_summary_
"""
from requests import Response
import json
from app.device.models import device_model as dev
from app.logger import logger_conf as log
from app.http import http_service as http

def get_nb_device_ips(key: str, ip: str):
    """
    Retrieves IP addresses from Netbox for a given key and IP.
    Args:
        key (str): The API key for authentication.
        ip (str): The IP address to query.
    Returns:
        list: A list of device IP addresses retrieved from Netbox.
    Raises:
        json.JSONDecodeError: If there is an error decoding the JSON response.
    Logs:
        Logs various debug information including the request URL, headers, and any errors encountered.
    """
    try:
        log.logger.debug("Getting Netbox devices ip")
        url: str ="ipam/ip-addresses/?assigned=true"
        nb_addresses: Response = http.get(key=key,ip=ip,url=url)
        log.logger.debug("%s %s",str(nb_addresses.request.url),str(nb_addresses.request.headers))
        nb_addresses = json.loads(nb_addresses.text)
        while True:
            next_url: str = nb_addresses['next']
            device_ips: str = json.dumps(nb_addresses["results"])
            device_ips = json.loads(device_ips)
            if next_url is None:
                break
            nb_addresses: Response = http.get(key,ip, url.join(str(next_url).split("ip-addresses")[1]))
            log.logger.debug("%s %s",str(nb_addresses.request.url),
                            str(nb_addresses.request.headers))
            nb_addresses = json.loads(nb_addresses.text)
        return device_ips
    except json.JSONDecodeError as e:
        log.logger.error("Error with getting ip addresses netbox ip addresses %s %s"
                         ,nb_addresses.text,str(e))
        return []

def get_nb_devices(key: str, ip: str):
    import requests
    NETBOX_GRAPHQL_URL = "http://your-netbox-instance/graphql/"
    API_TOKEN = "your_api_token_here"

    # Define headers
    headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json"
    }

    query = """
    {
      device_list {
        id
        name
        interfaces {
          name
          mac_address
          ip_addresses {
            address
          }
        }
      }
    }
    """

    response: Response = requests.post(NETBOX_GRAPHQL_URL, headers=headers, json={"query": query})

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print(f"GraphQL Errors: {data['errors']}")
        else:
            devices = data["data"]["device_list"]
            devices_with_ips = [
                device for device in devices
                if any(iface["ip_addresses"] for iface in device["interfaces"])
            ]
            for device in devices_with_ips:
                print(f"Device ID: {device['id']}, Name: {device['name']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

