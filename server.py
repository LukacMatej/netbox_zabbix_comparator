"""server.py
Tested with Netbox version v4.5.2 and Zabbix version 7.4.2
This script sets up a Flask web server
with routes for handling webhooks and a test route.
It also includes an argument parser
for configuring the server to run in development or production mode.
Routes:
    /webhook (POST): Executes a subprocess to run a Python script for syncing NetBox and Zabbix.
    / (GET): Renders an index.html template to check if the server is up and running.
Functions:
    webhook(): Handles POST requests to the /webhook route and runs a subprocess.
    test(): Renders an index.html template to check if the server is up and running.
    parser_init(): Initializes and returns an argument parser for server configuration.
Usage:
    Run the script with optional arguments to start the server in development or production mode.
    Example:
        python server.py --development
        python server.py --debug
Environment Variables:
    LISTEN_ADDRESS: The IP address the server will listen on.
    HTTP_PORT: The port the server will listen on.
Dependencies:
    - Flask
    - subprocess
    - argparse
    - os
"""

from __future__ import annotations

import argparse
import os
import requests
from flask import Flask, render_template
from waitress import serve
from app.compare.service import compare_service as ct
from app.compare.service import synchronization_service as ss
from app.device.models.synchonization_output_model import SyncOutput as sync_output_model
from app.device.service import device_service as ds
from app.device.models.difference_model import DeviceDifference
from app.device.models.device_model import Device
from app.logger import logger_conf as log

app = Flask(__name__)


@app.route("/")
def test() -> tuple[str, int]:
    """
    A test route to check if the server is up and running.

    Returns:
        str: A message indicating that the server is up and running.
    """
    return render_template("index.html"), 200


@app.route("/RunCompare")
def run_compare() -> tuple[str, int]:
    """
    Compare devices between Netbox and Zabbix systems.
    Retrieves API credentials and IP addresses from environment variables,
    performs a comparison between Netbox and Zabbix devices, and returns
    the comparison results rendered in an HTML template.
    Environment Variables:
        NETBOX_KEY: API key for Netbox authentication
        NETBOX_IP: IP address or hostname of Netbox server
        ZABBIX_IP: IP address or hostname of Zabbix server
        ZABBIX_KEY: API key for Zabbix authentication
    Returns:
        tuple[str, int]: A tuple containing:
            - str: HTML content of the comparison results or error message
            - int: HTTP status code (200 on success, 500 on error)
    Raises:
        Implicitly handles exceptions from the compare operation and returns
        them as error responses with status code 500.
    """
    netbox_key: str | None = os.environ.get("NETBOX_KEY")
    netbox_ip: str | None = os.environ.get("NETBOX_IP")
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    compare_output: Exception | tuple[list[DeviceDifference], list[Device], list[Device]] = (
        ct.compare(nb_ip=netbox_ip, nb_key=netbox_key, zb_ip=zabbix_ip, zb_key=zabbix_key)
    )
    if isinstance(compare_output, Exception):
        return str(compare_output), 500
    differences: list[DeviceDifference] = compare_output[0]
    netbox_devices: list[Device] = compare_output[1]
    zabbix_devices: list[Device] = compare_output[2]
    log.logger.debug(ds.print_differences(differences))
    log.logger.debug(ds.print_devices(netbox_devices))
    log.logger.debug(ds.print_devices(zabbix_devices))
    display_differences, display_netbox_devices, display_zabbix_devices = ds.uniform_output_text(
        differences,
        netbox_devices,
        zabbix_devices,
    )
    return (
        render_template(
            "compare_output.html",
            differences=display_differences,
            netbox_devices=display_netbox_devices,
            zabbix_devices=display_zabbix_devices,
            netbox_url=netbox_ip,
            zabbix_url=zabbix_ip,
        ),
        200,
    )


@app.route("/RunCompareSync")
def run_compare_sync() -> tuple[str, int]:
    """
    Execute a comparison and synchronization between NetBox and Zabbix devices.
    Retrieves NetBox and Zabbix credentials from environment variables, performs
    a comparison of devices between the two systems, logs the differences and
    devices found, synchronizes the devices, and renders a comparison output
    template with the results.
    Returns:
        tuple[str, int]: A tuple containing:
            - str: Rendered HTML template string with comparison results and
                   synchronization status, or error message
            - int: HTTP status code (200 for success, 500 for error)
    Raises:
        (Implicitly) Returns error status if comparison fails.
    Environment Variables Required:
        - NETBOX_KEY: API key for NetBox authentication
        - NETBOX_IP: NetBox server IP/URL
        - ZABBIX_IP: Zabbix server IP/URL
        - ZABBIX_KEY: API key for Zabbix authentication
    """
    synchronization: bool = True
    sync_output: sync_output_model
    netbox_key: str | None = os.environ.get("NETBOX_KEY")
    netbox_ip: str | None = os.environ.get("NETBOX_IP")
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    compare_output: Exception | tuple[list[DeviceDifference], list[Device], list[Device]] = (
        ct.compare(nb_ip=netbox_ip, nb_key=netbox_key, zb_ip=zabbix_ip, zb_key=zabbix_key)
    )
    if isinstance(compare_output, Exception):
        return str(compare_output), 500
    differences: list[DeviceDifference] = compare_output[0]
    netbox_devices: list[Device] = compare_output[1]
    zabbix_devices: list[Device] = compare_output[2]
    log.logger.debug(ds.print_differences(differences))
    log.logger.debug(ds.print_devices(netbox_devices))
    log.logger.debug(ds.print_devices(zabbix_devices))
    sync_output: sync_output_model = ss.sync_netbox_zabbix_devices(
        netbox_devices=netbox_devices, zabbix_devices=zabbix_devices, differences=differences
    )
    log.logger.debug("Synchronization Output: %s", sync_output)
    display_differences, display_netbox_devices, display_zabbix_devices = ds.uniform_output_text(
        differences,
        netbox_devices,
        zabbix_devices,
    )
    return (
        render_template(
            "compare_output.html",
            sync_output=sync_output,
            synchronization=synchronization,
            differences=display_differences,
            netbox_devices=display_netbox_devices,
            zabbix_devices=display_zabbix_devices,
            netbox_url=netbox_ip,
            zabbix_url=zabbix_ip,
        ),
        200,
    )

def test_connection() -> tuple[str, int]:
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    netbox_ip: str | None = os.environ.get("NETBOX_IP")
    netbox_key: str | None = os.environ.get("NETBOX_KEY")
    if not zabbix_ip or not zabbix_key:
        return "Zabbix credentials not set in environment variables.", 500
    if not netbox_ip or not netbox_key:
        return "NetBox credentials not set in environment variables.", 500
    netbox_headers: dict[str, str] = {
        "Authorization": f"Token {netbox_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    zabbix_headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    data = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": [],
        "id": 1,
    }
    try:
        netbox_response: requests.Response = requests.get(f"{netbox_ip}/api", headers=netbox_headers, timeout=10)
        netbox_response.raise_for_status()
    except requests.RequestException as e:
        return f"Error connecting to NetBox: {e}", 500

    try:
        zabbix_response: requests.Response = requests.post(f"{zabbix_ip}api_jsonrpc.php", headers=zabbix_headers, json=data, timeout=10)
        zabbix_response.raise_for_status()
    except requests.RequestException as e:
        return f"Error connecting to Zabbix: {e}", 500

    return "Connection to Zabbix and NetBox successful.", 200

def parser_init() -> argparse.ArgumentParser:
    """
    Initialize the argument parser for the server.

    Returns:
        argparse.ArgumentParser: The argument parser object.
    """
    argparser = argparse.ArgumentParser(description="Turn on/off production.")
    argparser.add_argument(
        "-d", "--development", help="Turn on development server", action="store_true"
    )
    argparser.add_argument("-debug", "--debug", help="Turn on debug mode", action="store_true")
    return argparser


if __name__ == "__main__":
    parser: argparse.ArgumentParser = parser_init()
    args: argparse.Namespace = parser.parse_args()
    response: tuple[str, int] = test_connection()
    if response[1] != 200:
        log.logger.error(response[0])
        exit(1)
    docker_ip: str = os.environ.get("LISTEN_ADDRESS", "0.0.0.0")
    docker_port: str | int = os.environ.get("HTTP_PORT", 7000)
    if not args.development:
        # production
        serve(app, host=docker_ip, port=docker_port)
    else:
        # development
        app.run(debug=True, host=docker_ip, port=docker_port)
