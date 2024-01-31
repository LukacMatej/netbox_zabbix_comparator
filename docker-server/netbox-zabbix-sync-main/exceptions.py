from pyzabbix import ZabbixAPIException
class SyncError(Exception):
    pass


class SyncExternalError(SyncError):
    pass


class SyncInventoryError(SyncError):
    pass


class SyncDuplicateError(SyncError):
    pass


class EnvironmentVarError(SyncError):
    pass


class InterfaceConfigError(SyncError):
    pass


class ProxyConfigError(SyncError):
    pass


class HostgroupError(SyncError):
    pass
