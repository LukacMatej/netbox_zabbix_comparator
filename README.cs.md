# Porovnání a synchronizace devices Netboxu a Zabbixu

Aplikace slouží k synchronizaci konfigurace zařízení (devices) mezi Netboxem a Zabbixem s možností porovnání a automatického vytváření/aktualizace zařízení v Zabbixu na základě konfigurace v Netboxu.

## Spuštění dockeru

```bash
docker run -d \
  -p <port>:<port> \
  -e LISTEN_ADDRESS=<IP adresa> \
  -e HTTP_PORT=<port> \
  -e ZABBIX_DEFAULT_HOSTGROUP=<název defaultní hostgroupy> \
  -e NETBOX_IP=<IP Adresa Netboxu s http:/> \
  -e NETBOX_KEY=<Netbox API klíč> \
  -e ZABBIX_IP=<IP Adresa Zabbixu s http:/> \
  -e ZABBIX_KEY=<Zabbix API klíč> \
  -e PROXY_ROOT_PATH=<dev|prod>
  netbox-zabbix
```

## Nastavení pro správný chod aplikace

### Priorita výběru Templates a Port Types

Systém používá hierarchickou prioritu při výběru Templates a Port Types. Aplikace hledá hodnoty v tomto pořadí (1 = nejvyšší priorita):

#### 1. Device Custom Fields (nejvyšší priorita)

Nastavit Custom Fields na individuální zařízení:

- `zabbix_templates` - seznam Zabbix šablon pro konkrétní zařízení
- `zabbix_port_type` - typ portu pro konkrétní zařízení

#### 2. Device Role Custom Fields

Nastavit Custom Fields na device role s výběrem Custom Field Choices:

- `zabbix_templates` - seznam šablon pro všechna zařízení s tímto rolem
- `zabbix_port_type` - typ portu pro všechna zařízení s tímto rolem

#### 3. Device Config Context (nejnižší priorita)

V Netboxu lze nastavit dědičný config context pro device role, který se automaticky aplikuje na všechna zařízení s danou rolí:

```json
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

**Důležité:** Pokud vyšší priorita neobsahuje hodnoty (je prázdná nebo None), systém automaticky přejde k nižší prioritě.

### Templates

* Šablony, které se budou aplikovat na zařízení v Zabbixu
* V Zabbixu musí existovat předem
* Podporuje více šablon najednou
* Je připraven Netbox script, který synchronizuje Custom Field Choices s názvem `zabbix_templates` s templates v Zabbixu, obdobný návod viz Zabbix hostgroups

### Port Type

* Specifikuje typ portu pro komunikaci s Zabbixem
* Podporované typy: Agent, SNMP, JMX, IPMI

### Primární IP adresa

* Povinné nastavení v Netboxu pro správný chod
* Používá se jako adresa pro připojení zařízení v Zabbixu
* Vybírá se z `primary_ip4` na zařízení

### Zabbix Host Groups

Je připraven Netbox script, který synchronizuje Custom Field Choices s názvem `zabbix_hostgroups` s host groups v Zabbixu:

- Custom Field Choices napojit na Custom Field s názvem `zabbix_hostgroups`
- Nastavit jako multi-select na DCIM > DEVICE
- Defaultní host group v Zabbixu je nastavena na "Netbox" pro kontrolu všech zařízení vytvořených synchronizací

### Custom Validation

Zabbix má mnoho závislostí ve vazbě Port Type - Templates, z toho důvodu byl vytvořen custom validation config, který komunikuje s zabbixem a řeší závislosti.

* Custom validátor volá endpoint jen v případě editace custom fields pro zabbix, viz výše

##### Postup:

Kam soubor `device_zabbix_validator.py` umístit a jak ho odkázat v `CUSTOM_VALIDATORS` závisí na tom, jak je NetBox nainstalovaný — obě varianty řeší importy Python modulů jinak.

**Instalace bez Dockeru (venv)**

* Vložit `device_zabbix_validator.py` do root složky netboxu (`netbox/netbox/`, vedle skutečného `configuration.py`) — tato složka je na Python path, takže je soubor importovatelný jako běžný top-level modul.
* Do `configuration/extra.py` (nebo přímo do `configuration.py`) vložit:
  ```python
  CUSTOM_VALIDATORS = {
      'dcim.device': (
          'device_zabbix_validator.ZabbixCustomFieldValidator',
      )
  }
  ```

**Instalace přes [netbox-docker](https://github.com/netbox-community/netbox-docker)**

* Vložit `device_zabbix_validator.py` do stejné hostitelské složky, která je připojená (bind-mount) do `/etc/netbox/config/` (typicky `configuration/`, vedle `configuration.py`/`extra.py`) — tato složka ale sama o sobě není na `sys.path`.
* Loader konfigurace v netbox-docker (`docker/configuration.docker.py`, který se uvnitř image stává skutečným `configuration.py`) načte každý `.py` soubor z této připojené složky, ale zaregistruje ho pod **zploštělým názvem modulu**: `netbox.configuration.<název_souboru>`, kde je každá tečka nahrazena podtržítkem. Pro `device_zabbix_validator.py` je výsledný název `netbox_configuration_device_zabbix_validator` — ne holý název souboru.
* Do `configuration/extra.py` vložit:
  ```python
  CUSTOM_VALIDATORS = {
      'dcim.device': (
          'netbox_configuration_device_zabbix_validator.ZabbixCustomFieldValidator',
      )
  }
  ```
* Restartovat (znovu vytvořit) kontejnery NetBoxu, aby se připojená konfigurace znovu načetla: `docker compose up -d netbox netbox-worker` (obyčejný `restart` nově přidaný soubor nenačte, protože z pohledu Compose se tím nic v konfiguraci kontejneru nemění).

Custom validátor volá API endpoint porovnávače /validate_update (port 7000, potřeba upravit pokud se používá jiný)

## REST API

Ovládání přes hamburger menu:

### Compare

- Spuštění porovnání zařízení v Netboxu a Zabbixu
- Zobrazí rozdíly a shody v konfiguraci

### Synchronize

- Spuštění jednosměrné synchronizace z Netboxu do Zabbixu
- Možné scénáře:
  - Zařízení existuje jen v Netboxu → vytvoří se v Zabbixu
  - Zařízení existuje v obou → hodnoty z Netboxu přepíšou hodnoty v Zabbixu (pokud se liší)
  - Zařízení je identické → se nic nestane
