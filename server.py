"""server.py
Tested with Netbox version v4.5.2 and Zabbix version 7.4.2
This script sets up a FastAPI web server
with Jinja2 templates and HTMX-friendly routes.
It also includes an argument parser
for configuring the server to run in development or production mode.
Routes:
    / (GET): Renders the index page.
    /run_comparison (GET): Compares devices between NetBox and Zabbix.
    /run_comparison_sync (GET): Compares and synchronizes devices.
Functions:
    test(): Renders an index template with actions for compare/sync.
    run_compare(): Returns comparison output in full page or HTMX partial mode.
    run_compare_sync(): Returns synchronized output in full page or HTMX partial mode.
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
    - FastAPI
    - uvicorn
    - argparse
    - os
"""

from __future__ import annotations

import argparse
import os
import sys

import requests
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from app.compare.service import compare_service as ct
from app.compare.service import synchronization_service as ss
from app.device.models.address_model import Address
from app.device.models.device_model import Device
from app.device.models.difference_model import DeviceDifference
from app.device.models.interface_model import Interface
from app.device.models.synchonization_output_model import (
    SyncOutput as sync_output_model,
)
from app.device.service import device_service as ds
from app.device.service import validator_service as validator
from app.logger import logger_conf as log

proxy_root_path: str = os.environ.get("PROXY_ROOT_PATH", "")
# Ensure root_path starts with / if provided
if proxy_root_path and not proxy_root_path.startswith("/"):
    proxy_root_path = "/" + proxy_root_path
app = FastAPI(root_path=proxy_root_path, title="NetBox Zabbix Compare")
templates = Jinja2Templates(directory="templates")


def dict_to_address(data: dict) -> Address:
    return Address(address=data["address"], dns_name=data["dns_name"])


def dict_to_interface(data: dict) -> Interface:
    return Interface(
        name=data["name"],
        addresses=[dict_to_address(a) for a in data["addresses"]],
        mac_address=data["mac_address"],
        port_type=data["port_type"],
    )


def dict_to_device(data: dict) -> Device:
    return Device(
        name=data["name"],
        interfaces=[dict_to_interface(i) for i in data["interfaces"]],
        hostgroup=data["hostgroup"],
        description=data["description"],
        templates=data["templates"],
        status=data["status"],
    )


def device_to_dict(device: Device) -> dict:
    """Converts a Device (plain class, not Pydantic) into a JSON-serializable dict."""
    return {
        "name": device.name,
        "hostgroup": device.hostgroup,
        "description": device.description,
        "templates": device.templates,
        "status": device.status,
        "interfaces": [
            {
                "name": interface.name,
                "mac_address": interface.mac_address,
                "port_type": interface.port_type,
                "addresses": [address.to_dict() for address in interface.addresses],
            }
            for interface in device.interfaces
        ],
    }


templates.env.globals["device_to_dict"] = device_to_dict


def difference_to_dict(difference: DeviceDifference) -> dict:
    """Converts a DeviceDifference into a JSON-serializable dict."""
    return {
        "nb_device": device_to_dict(difference.nb_device),
        "zb_device": device_to_dict(difference.zb_device),
        "differences": list(difference.differences),
    }


templates.env.globals["difference_to_dict"] = difference_to_dict


@app.get("/", response_class=HTMLResponse)
def test(request: Request) -> HTMLResponse:
    """
    A test route to check if the server is up and running.

    Returns:
        str: A message indicating that the server is up and running.
    """
    netbox_url: str | None = os.environ.get("NETBOX_IP")
    zabbix_url: str | None = os.environ.get("ZABBIX_IP")
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "netbox_url": netbox_url, "zabbix_url": zabbix_url},
        status_code=200,
    )


@app.post(
    "/create_zabbix_device", name="create_zabbix_device", response_class=HTMLResponse
)
async def create_zabbix_device(request: Request) -> Response:
    try:
        payload = await request.json()
    except ValueError:
        return PlainTextResponse("Invalid or missing JSON body", status_code=400)

    device = dict_to_device(payload)
    log.logger.info(f"Creating Zabbix device for device_id: {device.name}")
    try:
        ss.create_zabbix_device(device, sync_output_model())
        success = True
    except Exception as e:  # pylint: disable=broad-except
        log.logger.error(
            "Failed to create Zabbix device for %s: %s", device.name, e, exc_info=True
        )
        success = False
        error_log = str(e)

    return templates.TemplateResponse(
        request,
        "sync_button_result.html",
        {"success": success, "error_log": error_log},
        status_code=200,
    )


@app.post(
    "/synchronize_zabbix_device",
    name="synchronize_zabbix_device",
    response_class=HTMLResponse,
)
async def synchronize_zabbix_device(request: Request) -> Response:
    try:
        payload = await request.json()
    except ValueError:
        return PlainTextResponse("Invalid or missing JSON body", status_code=400)

    nb_device = dict_to_device(payload["nb_device"])
    zb_device = dict_to_device(payload["zb_device"])
    difference = DeviceDifference(
        nb_device=nb_device,
        zb_device=zb_device,
        differences=tuple(payload["differences"]),
    )

    log.logger.info(f"Synchronizing Zabbix device: {nb_device} -> {zb_device}")
    sync_output = sync_output_model()
    try:
        ss.apply_differences(differences=difference, sync_output=sync_output)
        if "Exception " in sync_output.synchronization_output_differences:
            raise Exception("Differences found: " + ", ".join(sync_output.synchronization_output_differences))
        success = True
    except Exception as e:  # pylint: disable=broad-except
        log.logger.error(
            "Synchronization failed for %s: %s", nb_device.name, e, exc_info=True
        )
        success = False
        error_log = str(e)

    return templates.TemplateResponse(
        request,
        "sync_button_result.html",
        {"success": success, "error_log": error_log},
        status_code=200,
    )


@app.get("/run_comparison", name="run_comparison", response_class=HTMLResponse)
def run_compare(request: Request) -> Response:
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
    compare_output: (
        Exception | tuple[list[DeviceDifference], list[Device], list[Device]]
    ) = ct.compare(
        nb_ip=netbox_ip, nb_key=netbox_key, zb_ip=zabbix_ip, zb_key=zabbix_key
    )
    if isinstance(compare_output, Exception):
        return PlainTextResponse(str(compare_output), status_code=500)
    differences: list[DeviceDifference] = compare_output[0]
    netbox_devices: list[Device] = compare_output[1]
    zabbix_devices: list[Device] = compare_output[2]
    log.logger.debug(ds.print_differences(differences))
    log.logger.debug(ds.print_devices(netbox_devices))
    log.logger.debug(ds.print_devices(zabbix_devices))
    formatted_output = ds.uniform_output_text(
        differences,
        netbox_devices,
        zabbix_devices,
    )
    if isinstance(formatted_output, tuple) and len(formatted_output) == 3:
        display_differences, display_netbox_devices, display_zabbix_devices = (
            formatted_output
        )
    else:
        display_differences = differences
        display_netbox_devices = netbox_devices
        display_zabbix_devices = zabbix_devices
    template_name = (
        "compare_output_content.html"
        if request.headers.get("hx-request", "").lower() == "true"
        else "compare_output.html"
    )
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "differences": display_differences,
            "netbox_devices": display_netbox_devices,
            "zabbix_devices": display_zabbix_devices,
            "netbox_url": netbox_ip,
            "zabbix_url": zabbix_ip,
            "synchronization": False,
            "sync_output": None,
        },
        status_code=200,
    )


@app.get(
    "/run_comparison_sync", name="run_comparison_sync", response_class=HTMLResponse
)
def run_compare_sync(request: Request) -> Response:
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
    compare_output: (
        Exception | tuple[list[DeviceDifference], list[Device], list[Device]]
    ) = ct.compare(
        nb_ip=netbox_ip, nb_key=netbox_key, zb_ip=zabbix_ip, zb_key=zabbix_key
    )
    if isinstance(compare_output, Exception):
        return PlainTextResponse(str(compare_output), status_code=500)
    differences: list[DeviceDifference] = compare_output[0]
    netbox_devices: list[Device] = compare_output[1]
    zabbix_devices: list[Device] = compare_output[2]
    log.logger.debug(ds.print_differences(differences))
    log.logger.debug(ds.print_devices(netbox_devices))
    log.logger.debug(ds.print_devices(zabbix_devices))
    formatted_output_result: tuple[
        list[DeviceDifference], list[Device], list[Device]
    ] = ds.uniform_output_text(
        differences,
        netbox_devices,
        zabbix_devices,
    )
    ds.map_port_type_device(netbox_devices, zabbix_devices, numbered=True)
    sync_output = ss.sync_netbox_zabbix_devices(
        netbox_devices=netbox_devices,
        zabbix_devices=zabbix_devices,
        differences=differences,
    )
    log.logger.debug("Synchronization Output: %s", sync_output)

    if isinstance(formatted_output_result, tuple) and len(formatted_output_result) == 3:
        display_differences, display_netbox_devices, display_zabbix_devices = (
            formatted_output_result
        )
    else:
        display_differences: list[DeviceDifference] = differences
        display_netbox_devices: list[Device] = netbox_devices
        display_zabbix_devices: list[Device] = zabbix_devices
    template_name = (
        "compare_output_content.html"
        if request.headers.get("hx-request", "").lower() == "true"
        else "compare_output.html"
    )
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "sync_output": sync_output,
            "synchronization": synchronization,
            "differences": display_differences,
            "netbox_devices": display_netbox_devices,
            "zabbix_devices": display_zabbix_devices,
            "netbox_url": netbox_ip,
            "zabbix_url": zabbix_ip,
        },
        status_code=200,
    )


@app.post("/webhook_create")
async def webhook_create(request: Request):
    """Handle webhook create event."""
    data = await request.json()
    nb_device: Device = ds.parse_webhook_create(data)
    log.logger.info("Webhook create event received: %s", data)
    log.logger.info(f"Creating Zabbix device for device_id: {nb_device.name}")
    try:
        ss.create_zabbix_device(nb_device, sync_output_model())
        response = "True"
        status_code = 200
    except Exception as e:  # pylint: disable=broad-except
        log.logger.error(
            "Failed to create Zabbix device for %s: %s",
            nb_device.name,
            e,
            exc_info=True,
        )
        response = str(e)
        status_code = 500
    return {"success": response}, status_code


@app.post("/webhook_update")
async def webhook_update(request: Request):
    """Handle webhook update event."""
    data = await request.json()
    log.logger.info("Webhook update event received: %s", data)

    nb_device = ds.parse_webhook_update(data)
    zb_device = ds.get_zabbix_device(nb_device.name)

    if zb_device is None:
        log.logger.info("No Zabbix host found for %s, skipping sync.", nb_device.name)
        return {"success": "True"}, 200

    differences = ct.compare_devices([nb_device], [zb_device])
    difference_list = differences[0]

    if not difference_list:
        log.logger.info("No differences found for %s.", nb_device.name)
        return {"success": "True"}, 200

    difference = difference_list[0]
    log.logger.info("Synchronizing Zabbix device: %s -> %s", nb_device, zb_device)

    sync_output = sync_output_model()
    try:
        ss.apply_differences(differences=difference, sync_output=sync_output)
        response = "True"
        status_code = 200
    except Exception as e:  # pylint: disable=broad-except
        log.logger.error(
            "Synchronization failed for %s: %s", nb_device.name, e, exc_info=True
        )
        response = str(e)
        status_code = 500

    return {"success": response}, status_code


@app.post("/webhook_delete")
async def webhook_delete(request: Request):
    """Handle webhook create event."""
    data = await request.json()
    nb_device: Device = ds.parse_webhook_delete(data)
    log.logger.info("Webhook delete event received: %s", data)
    log.logger.info(f"Deleting Zabbix device for device_id: {nb_device.name}")
    try:
        ds.delete_zabbix_device(nb_device)
        response = "True"
        status_code = 200
    except Exception as e:  # pylint: disable=broad-except
        log.logger.error(
            "Failed to delete Zabbix device for %s: %s",
            nb_device.name,
            e,
            exc_info=True,
        )
        response = str(e)
        status_code = 500
    return {"success": response}, status_code


@app.post("/validate_update")
async def validate_update(request: Request):
    """Validate device update against Zabbix configuration.

    Args:
        request: The incoming request containing device update data.

    Returns:
        JSONResponse: Validation result with 'valid' (bool) and 'message' (str).
    """
    data = await request.json()
    event_type = data.get("event", "unknown")
    device_name = data.get("data", {}).get("name", "unknown")

    log.logger.info(
        "Validation request received: event=%s, device=%s",
        event_type,
        device_name,
    )
    log.logger.debug("Full request data: %s", data)

    if event_type not in ["updated", "created", "deleted"]:
        log.logger.warning(
            "Invalid event type: %s (expected 'updated', 'created', or 'deleted')",
            event_type,
        )
        return JSONResponse(
            {"valid": False, "message": "Invalid event type"},
            status_code=400,
        )

    try:
        result = validator.can_update_device(data)
    except Exception as e:  # pylint: disable=broad-except
        log.logger.error(
            "Exception validating device %s: %s",
            device_name,
            e,
            exc_info=True,
        )
        return JSONResponse(
            {"valid": False, "message": str(e)},
            status_code=500,
        )

    if isinstance(result, Exception):
        log.logger.error(
            "Validation error for device %s: %s",
            device_name,
            result,
        )
        return JSONResponse(
            {"valid": False, "message": str(result)},
            status_code=500,
        )

    log.logger.info(
        "Validation completed: device=%s, valid=%s, message=%s",
        device_name,
        result.get("valid"),
        result.get("message"),
    )

    return JSONResponse(result, status_code=200)


def test_connection() -> tuple[str, int]:
    """
    Test connection to NetBox and Zabbix servers.

    Validates that credentials are set in environment variables and tests HTTP
    connectivity to both services.

    Returns:
        tuple[str, int]: A tuple containing status message and HTTP status code.
    """
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
        netbox_response: requests.Response = requests.get(
            f"{netbox_ip}/api", headers=netbox_headers, timeout=10
        )
        netbox_response.raise_for_status()
    except requests.RequestException as e:
        return f"Error connecting to NetBox: {e}", 500

    try:
        zabbix_response: requests.Response = requests.post(
            f"{zabbix_ip}api_jsonrpc.php",
            headers=zabbix_headers,
            json=data,
            timeout=10,
        )
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
    argparser.add_argument(
        "-debug", "--debug", help="Turn on debug mode", action="store_true"
    )
    return argparser


if __name__ == "__main__":
    parser: argparse.ArgumentParser = parser_init()
    args: argparse.Namespace = parser.parse_args()
    response: tuple[str, int] = test_connection()
    if response[1] != 200:
        log.logger.error(response[0])
        sys.exit(1)
    docker_ip: str = os.environ.get("LISTEN_ADDRESS", "0.0.0.0")
    docker_port: str | int = os.environ.get("HTTP_PORT", "7000")
    uvicorn.run(
        "server:app",
        host=docker_ip,
        port=int(docker_port),
        reload=args.development,
        log_level="debug" if args.debug else "info",
    )
