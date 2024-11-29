from dataclasses import dataclass
import requests
import json
import logger_conf as log
    
def get_nb_addresses(ip,key) -> list:
    """
    Retrieves NetBox addresses and converts them into a list of Reservation objects.
    Args:
        url (str): The URL to retrieve the NetBox addresses from.
        headers (dict): The headers to include in the request.
    Returns:
        list[pw.Reservation]: A list of Reservation objects containing the retrieved addresses.
    """
    try:
        headers = {
        "Authorization": f"Token {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
        }
        log.logger.debug("Getting Netbox ip addresses")
        n_reservs = []
        url = str(ip)+"/api/ipam/ip-addresses/?assigned=true"
        nb_addresses = requests.get(url, headers=headers,timeout=300)
        log.logger.debug("%s %s",str(nb_addresses.request.url),str(nb_addresses.request.headers))
        nb_addresses = json.loads(nb_addresses.text)
        while True:
            next_url = nb_addresses['next']
            n_addresses = json.dumps(nb_addresses["results"])
            n_addresses = json.loads(n_addresses)
            if next_url is None:
                break
            nb_addresses = requests.get(next_url, headers=headers,timeout=300)
            log.logger.debug("%s %s",str(nb_addresses.request.url),
                            str(nb_addresses.request.headers))
            nb_addresses = json.loads(nb_addresses.text)
        log.logger.debug("Finished getting netbox ip addresses")
        return n_reservs
    except json.JSONDecodeError as e:
        log.logger.error("Error with getting ip addresses netbox ip addresses %s %s"
                         ,nb_addresses.text,str(e))
        return []

def getZabbixDevices():
    pass

