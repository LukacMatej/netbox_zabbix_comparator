class SyncOutput:
    def __init__(self, synchronization_output_differences: list[str] = [],
                 synchronization_output_netbox: list[str] = [],
                 synchronization_output_zabbix: list[str] = []) -> None:
        """Initializes the synchronization output model with optional lists for differences, Netbox outputs, and Zabbix outputs."""
        self.synchronization_output_differences: list[str] = synchronization_output_differences
        self.synchronization_output_netbox: list[str] = synchronization_output_netbox
        self.synchronization_output_zabbix: list[str] = synchronization_output_zabbix
        
    def add_difference(self, difference: str):
        """Adds a difference to the synchronization output."""
        self.synchronization_output_differences.append(difference)
    
    def add_netbox_output(self, output: str):
        """Adds a Netbox output to the synchronization output."""
        self.synchronization_output_netbox.append(output)
    
    def add_zabbix_output(self, output: str):
        """Adds a Zabbix output to the synchronization output."""
        self.synchronization_output_zabbix.append(output)