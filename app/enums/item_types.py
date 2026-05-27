"""
Zabbix Item Types enumeration.

This module defines the ItemTypes enum based on Zabbix item type values.
Reference: https://www.zabbix.com/documentation/current/en/manual/api/reference/item/object
"""

from enum import Enum


class ItemTypes(Enum):
    """
    Enumeration of Zabbix item types.

    Attributes:
        ZABBIX_AGENT: Zabbix agent
        ZABBIX_TRAPPER: Zabbix trapper
        SIMPLE_CHECK: Simple check
        ZABBIX_INTERNAL: Zabbix internal
        ZABBIX_AGENT_ACTIVE: Zabbix agent (active)
        WEB_ITEM: Web item
        EXTERNAL_CHECK: External check
        DATABASE_MONITOR: Database monitor
        IPMI_AGENT: IPMI agent
        SSH_AGENT: SSH agent
        TELNET_AGENT: TELNET agent
        CALCULATED: Calculated
        JMX_AGENT: JMX agent
        SNMP_TRAP: SNMP trap
        DEPENDENT_ITEM: Dependent item
        HTTP_AGENT: HTTP agent
        SNMP_AGENT: SNMP agent
        SCRIPT: Script
        BROWSER: Browser
    """

    ZABBIX_AGENT = 0
    ZABBIX_TRAPPER = 2
    SIMPLE_CHECK = 3
    ZABBIX_INTERNAL = 5
    ZABBIX_AGENT_ACTIVE = 7
    WEB_ITEM = 9
    EXTERNAL_CHECK = 10
    DATABASE_MONITOR = 11
    IPMI_AGENT = 12
    SSH_AGENT = 13
    TELNET_AGENT = 14
    CALCULATED = 15
    JMX_AGENT = 16
    SNMP_TRAP = 17
    DEPENDENT_ITEM = 18
    HTTP_AGENT = 19
    SNMP_AGENT = 20
    SCRIPT = 21
    BROWSER = 22
