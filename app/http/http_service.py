"""
    This module provides HTTP service functions to interact with a RESTful API using GET, POST, PATCH, and DELETE requests.
    Functions:
        get_headers(key: str) -> dict:
        get(key: str, ip: str, url: str) -> tuple[str, int]:
        post(key: str, ip: str, url: str, json_data: Any) -> tuple[str, int]:
        patch(key: str, ip: str, url: str, json_data: Any) -> tuple[str, int]:
        delete(key: str, ip: str, url: str) -> tuple[str, int]:
    """
from typing import Any
import requests

def get_headers(key: str) -> dict:
    """
    Generate HTTP headers for authorization and content type.

    Args:
        key (str): The authorization token to be included in the headers.

    Returns:
        dict: A dictionary containing the HTTP headers.
    """
    return {
        "Authorization": f"Token {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def get(key: str,ip: str) -> tuple[str, int]:
    """
    Sends a GET request to the specified IP address and URL with the provided API key.

    Args:
        key (str): The API key for authentication.
        ip (str): The IP address of the server.
        url (str): The specific endpoint to be accessed.

    Returns:
        tuple[str, int]: A tuple containing the response content as a string and the HTTP status code as an integer.
    """
    response: requests.Response = requests.get(
        f"{ip}", headers=get_headers(key), timeout=300)
    return response

def post(key: str, ip: str, url: str, json_data: Any) -> tuple[str, int]:
    """
    Sends a POST request to the specified URL with the given JSON data.

    Args:
        key (str): The API key for authentication.
        ip (str): The IP address of the server.
        url (str): The endpoint URL to send the request to.
        json_data (Any): The JSON data to include in the request body.

    Returns:
        tuple[str, int]: A tuple containing the response text and the status code.
    """
    response: requests.Response = requests.post(
        f"{ip}/api/{url}", headers=get_headers(key), data=json_data, timeout=300)
    return response

def patch(key: str, ip: str, url: str, json_data: Any) -> tuple[str, int]:
    """
    Sends a PATCH request to the specified URL with the given JSON data.

    Args:
        key (str): The API key for authentication.
        ip (str): The IP address of the server.
        url (str): The endpoint URL to send the request to.
        json_data (Any): The JSON data to be sent in the request body.

    Returns:
        tuple[str, int]: A tuple containing the response text and status code.
    """
    response: requests.Response = requests.patch(
        f"{ip}/api/{url}", headers=get_headers(key), data=json_data, timeout=300)
    return response

def delete(key: str, ip: str, url: str) -> tuple[str, int]:
    """
    Sends a DELETE request to the specified URL.

    Args:
        key (str): The API key for authentication.
        ip (str): The IP address of the server.
        url (str): The endpoint URL to send the DELETE request to.

    Returns:
        tuple[str, int]: A tuple containing the response text and the status code.
    """
    response: requests.Response = requests.delete(
        f"{ip}/api/{url}", headers=get_headers(key), timeout=300)
    return response
