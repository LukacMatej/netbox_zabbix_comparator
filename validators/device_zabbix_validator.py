import requests
from extras.validators import CustomValidator

class ZabbixCustomFieldValidator(CustomValidator):

    def validate(self, instance, request):
        # 1. Define the custom fields we want to monitor
        TARGET_FIELDS = {"zabbix_port_type", "zabbix_templates"}

       # 2. Grab the pre-change snapshot
        snapshot = getattr(instance, "_prechange_snapshot", None)

        if snapshot:
            # FIX: The serialized snapshot dictionary uses 'custom_fields'
            old_cfs = snapshot.get("custom_fields", {})

            # The unsaved python object instance uses 'custom_field_data'
            new_cfs = getattr(instance, "custom_field_data", {})

            # Compare old vs new array values for our target fields
            any_changed = any(
                new_cfs.get(field) != old_cfs.get(field)
                for field in TARGET_FIELDS
            )

            # If neither field was modified, exit immediatelytest
            if not any_changed:
                return

        # 3. Manually construct the data payload.
        # Do NOT use DeviceSerializer here, as the instance relationships are not yet safely saved.
        new_cfs = getattr(instance, "custom_field_data", {})

        serialized_data = {
            "id": instance.id,
            "name": instance.name,
            "status": instance.status,
            "device_type": instance.device_type.model if hasattr(instance, 'device_type') and instance.device_type else None,
            "device_role": instance.device_role.name if hasattr(instance, 'device_role') and instance.device_role else None,
            "site": instance.site.name if hasattr(instance, 'site') and instance.site else None,
            "custom_fields": new_cfs
        }

        # 4. Combine everything into your payload structure
        payload = {
            "event": "updated" if snapshot else "created",
            "object_type": "dcim.device",
            "username": request.user.username if request and hasattr(request, 'user') else "system",
            "request_id": str(getattr(request, 'id', '')) if request else "",
            "data": serialized_data
        }

        # 5. Fire off the synchronous validation request
        try:
            response = requests.post(
                "http://192.168.201.48:7000/validate_update",
                json=payload,
                timeout=3.0,
            )

            if response.status_code != 200:
                self.fail(
                    f"External validation service returned HTTP {response.status_code}, error: {response.text}"
                )

            result = response.json()
            if not result.get("valid", False):
                error_msg = result.get(
                    "message", "Rejected by external Zabbix validation engine."
                )
                self.fail(error_msg)

        except requests.exceptions.Timeout:
            self.fail("Validation failed: The external validation service timed out.")
        except requests.exceptions.RequestException as e:
            self.fail(f"Validation failed: Unable to reach validation server ({str(e)}).")
