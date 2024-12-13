"""server.py
This script sets up a Flask web server with routes for handling webhooks and a test route. 
It also includes an argument parser for configuring the server to run in development or production mode.
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
from flask import Flask, render_template, request
from waitress import serve
import subprocess
import argparse
import os
from app.compare.service import compare_service as ct
from app.device.service import device_service as ds
from app.device.models.difference_model import DeviceDifference
from app.device.models.device_model import Device
from app.logger import logger_conf as log

app = Flask(__name__)

@app.route('/webhook',methods=['POST'])
def webhook() -> tuple[str,int]:
    if request.method == 'POST':
        subprocess.run(["python",'netbox-zabbix-sync-main/netbox_zabbix_sync.py'])
        return 'success', 200
    else:
        return 'error',400

@app.route("/")
def test() -> tuple[str,int]:
    """
    A test route to check if the server is up and running.

    Returns:
        str: A message indicating that the server is up and running.
    """
    return render_template(
        "index.html"
        ),200
    
@app.route("/RunCompare")
def RunCompare() -> tuple[str, int]:
    netbox_key: str = os.environ.get("NETBOX_KEY")
    netbox_ip: str = os.environ.get("NETBOX_IP")
    zabbix_ip: str = os.environ.get("ZABBIX_IP")
    zabbix_key: str = os.environ.get("ZABBIX_KEY")
    NETBOX_IP="http://172.26.248.142:8000"
    NETBOX_KEY="8f9d3eaba15b0fb9c182f316ee9ee7f791ab0e4b"
    ZABBIX_IP="http://172.26.248.142:80"
    ZABBIX_KEY="14a116237840d411e877d16b511eecc00818a3c050470648db9a91d2326e00f5"
    compare_output: Exception | tuple[list[DeviceDifference], list[Device], list[Device]] = ct.compare(nb_ip=NETBOX_IP, nb_key=NETBOX_KEY, zb_ip=ZABBIX_IP, zb_key=ZABBIX_KEY)
    if isinstance(compare_output, Exception):
        return str(compare_output), 500
    differences: list[DeviceDifference] = compare_output[0]
    netbox_devices: list[Device] = compare_output[1]
    zabbix_devices: list[Device] = compare_output[2]
    log.logger.debug(differences)
    log.logger.debug(netbox_devices)
    log.logger.debug(zabbix_devices)
    return render_template(
        "compare_output.html",
        differences=compare_output[0],
        netbox_devices=compare_output[1],
        zabbix_devices=compare_output[2]
    ), 200
        
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
    docker_ip: str = os.environ.get("LISTEN_ADDRESS","0.0.0.0")
    docker_port: str = os.environ.get("HTTP_PORT",7000)
    if not args.development:
        # production
        serve(app, host=docker_ip, port=docker_port)
    else:
        # development
        app.run(debug=True, host=docker_ip, port=docker_port)
