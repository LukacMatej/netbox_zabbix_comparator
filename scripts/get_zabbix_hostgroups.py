import requests
from extras.scripts import Script, StringVar  # pylint: disable=import-error
from extras.models import CustomFieldChoiceSet  # pylint: disable=import-error

class SyncZabbixHostgroups(Script):
    class Meta:
        name = "Sync Zabbix Hostgroups"
        description = "Pulls hostgroups from Zabbix API and updates the 'zabbix_hostgroups' Custom Field Choice Set."

    zabbix_url = StringVar(
        description="Zabbix API URL (e.g., https://zabbix.example.com/zabbix/api_jsonrpc.php)"
    )
    zabbix_token = StringVar(
        description="Zabbix API Token (sent as Authorization: Bearer <token>)"
    )

    def run(self, data, commit):
        url = data['zabbix_url']

        # Zabbix JSON-RPC payload
        payload = {
            "jsonrpc": "2.0",
            "method": "hostgroup.get",
            "params": {
                "output": ["name"],
                "sortfield": "name"
            },
            "id": 1
        }

        headers = {
            "Authorization": f"Bearer {data['zabbix_token']}",
            "Content-Type": "application/json",
        }

        try:
            # 1. Fetch from Zabbix
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            result = response.json()

            if 'error' in result:
                self.log_failure(f"Zabbix Error: {result['error'].get('data', 'Unknown error')}")
                return

            # Extract and sort the group names
            group_names = sorted([g['name'] for g in result['result']])
            self.log_info(f"Retrieved {len(group_names)} groups from Zabbix.")

            # 2. Update NetBox Custom Field Choice Set
            try:
                choice_set = CustomFieldChoiceSet.objects.get(name='zabbix_hostgroups')

                # NetBox 4.x expects extra_choices to be a list of lists: [[value, label], [value, label]]
                formatted_choices = [[name, name] for name in group_names]
                formatted_choices.append(["Netbox","Netbox"])

                choice_set.extra_choices = formatted_choices
                choice_set.save()

                self.log_success(f"Successfully updated Custom Field Choice Set '{choice_set.name}' with {len(group_names)} choices.")

            except CustomFieldChoiceSet.DoesNotExist:
                self.log_failure("Custom Field Choice Set 'zabbix_hostgroups' not found. Please create it under Customization > Custom Field Choices.")

        except Exception as e:
            self.log_failure(f"Script execution failed: {str(e)}")
