import requests
from extras.scripts import Script, StringVar  # pylint: disable=import-error
from extras.models import CustomFieldChoiceSet  # pylint: disable=import-error

class SyncZabbixTemplates(Script):
    class Meta:
        name = "Sync Zabbix Templates"
        description = "Pulls templates from Zabbix API and updates the 'zabbix_templates' Custom Field Choice Set."

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
            "method": "template.get",
            "params": {
                "output": ["templateid", "name"],
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

            # Extract and sort the template names
            template_names = sorted([t['name'] for t in result['result']])
            self.log_info(f"Retrieved {len(template_names)} templates from Zabbix.")

            # 2. Update NetBox Custom Field Choice Set
            try:
                choice_set = CustomFieldChoiceSet.objects.get(name='zabbix_templates')

                # NetBox 4.x expects extra_choices to be a list of lists: [[value, label], [value, label]]
                formatted_choices = [[t['name'], t['name']] for t in result['result']]

                choice_set.extra_choices = formatted_choices
                choice_set.save()

                self.log_success(f"Successfully updated Custom Field Choice Set '{choice_set.name}' with {len(template_names)} choices.")

            except CustomFieldChoiceSet.DoesNotExist:
                self.log_failure("Custom Field Choice Set 'zabbix_templates' not found. Please create it under Customization > Custom Field Choices.")

        except Exception as e:
            self.log_failure(f"Script execution failed: {str(e)}")
