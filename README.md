# Porovnání a synchonizace devices Netboxu a Zabbixu

### Spuštění dockeru

docker run -d -p `<port:port>` -e LISTEN_ADDRESS=`<IP adresa>` -e HTTP_PORT=`<port>` -e NETBOX_IP=`<IP Adresa Netboxu s />` -e NETBOX_KEY=`<Netbox API klíč>` -e ZABBIX_IP=`<IP Adresa Zabbixu s />` -e ZABBIX_KEY=`<Zabbix API klíč>`netbox-zabbix

### Důležité věci na nastavení před startem

Nastavit v netboxu config contexty pro devices v formátu

V netboxu je možné nastavit dědičnej config context pro device role

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


### REST API

- /RunCompare
  - Spuštění porovnání zařízení v netboxu a zabbixu
- /RunCompareSync
  - Spuštění synchronizace, synchronizace je jedním směrem, z netboxu do zabbixu
  - Pokud zařízení exisutuje jen v Netboxu, vytvoří se i v zabixu
  - Pokud zařízení existuje v Netboxu a Zabbixu a jsou stejné, tak se nic nestane
  - Pokud zařízení existuje v Netboxu a Zabbixu, ale jejich hodnoty se liší, tak se přepíšou hodnoty z Netboxu do Zabbixu
