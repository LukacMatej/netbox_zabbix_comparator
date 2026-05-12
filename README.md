# Porovnání a synchonizace devices Netboxu a Zabbixu

### Spuštění dockeru

docker run -d -p `<port:port>` -e LISTEN_ADDRESS=`<IP adresa>` -e HTTP_PORT=`<port>` -e ZABBIX_DEFAULT_HOSTGROUP=`<název defaultní hostgroupy>` -e NETBOX_IP=`<IP Adresa Netboxu s />` -e NETBOX_KEY=`<Netbox API klíč>` -e ZABBIX_IP=`<IP Adresa Zabbixu s />` -e ZABBIX_KEY=`<Zabbix API klíč>`netbox-zabbix

### Důležité věci na nastavení pro správný chod porovnání

Priorita výběru templates je určena body - 1. nejvyšší priorita

Stačí splnit jeden bod:

##### 1. Device Custom Field

Nastavit Custom Field zabbix_templates na devices s výběrem Custom Field Choices zabbix_templates

##### 2. Device role Custom Field

Nastavit Custom Field zabbix_templates na device roles s výběrem Custom Field Choices zabbix_templates

##### 3. Device Roles Config Context

V netboxu je možné nastavit dědičnej config context pro device role, který se zobrazí na každém zařízení s tou rolí

```
{
    "zabbix": {
        "port_type": [
            "Agent"
        ],
        "templates": [
            "Template1",
	    "Template2"
        ]
    }
}
```

Templates

* Templaty, které se budou aplikovat na zařízení v Zabbixu, v zabbixu musí existovat předem.

Port Type

* Upřesnění typu portu pro zabbix
* Agent, SNMP, JMX, IPMI

Potřeba nastavit primární IP adresu v Netboxu, podle které bude fungovat v Zabbixu

Pro přidávání netbox zařízení do hostgroups v zabbixu je připraven netbox script, který synchronizuje Custom Field Choices s jménem zabbix_hostgroups s hostgroups v zabbixu, včetně defaultní hostgroup v zabbixu "Netbox" pro kontrolu všech zařízení vytvořených synchronizací.

Custom Field Choices napojit na Custom Field s jménem zabbix_hostgroups s multi-select na DCIM > DEVICE

### REST API

- /RunCompare
  - Spuštění porovnání zařízení v netboxu a zabbixu
- /RunCompareSync
  - Spuštění synchronizace, synchronizace je jedním směrem, z netboxu do zabbixu
  - Pokud zařízení exisutuje jen v Netboxu, vytvoří se i v zabixu
  - Pokud zařízení existuje v Netboxu a Zabbixu a jsou stejné, tak se nic nestane
  - Pokud zařízení existuje v Netboxu a Zabbixu, ale jejich hodnoty se liší, tak se přepíšou hodnoty z Netboxu do Zabbixu
