import logging
import argparse
# Set logging
def loggin_init(path):
    log_format = logging.Formatter('%(asctime)s - %(name)s - '
                                   '%(levelname)s - %(message)s')
    lgout = logging.StreamHandler()
    lgout.setFormatter(log_format)
    lgout.setLevel(logging.DEBUG)

    lgfile = logging.FileHandler(path.join(path.dirname(
                                 path.realpath(__file__)), "sync.log"))
    lgfile.setFormatter(log_format)
    lgfile.setLevel(logging.DEBUG)
    logger = logging.getLogger("Netbox-Zabbix-sync")
    logger.addHandler(lgout)
    logger.addHandler(lgfile)
    logger.setLevel(logging.WARNING)
    
    return logger
def parser_init():
    # Arguments parsing
    parser = argparse.ArgumentParser(
        description='A script to sync Zabbix with Netbox device data.'
    )
    parser.add_argument("-v", "--verbose", help="Turn on debugging.",
                        action="store_true")
    parser.add_argument("-c", "--cluster", action="store_true",
                        help=("Only add the primary node of a cluster "
                              "to Zabbix. Usefull when a shared virtual IP is "
                              "used for the control plane."))
    parser.add_argument("-H", "--hostgroups",
                        help="Create Zabbix hostgroups if not present",
                        action="store_true")
    parser.add_argument("-l", "--layout", type=str,
                        help="Defines the hostgroup layout",
                        default='site/manufacturer/dev_role')
    parser.add_argument("-p", "--proxy_power", action="store_true",
                        help=("USE WITH CAUTION. If there is a proxy "
                              "configured in Zabbix but not in Netbox, sync "
                              "the device and remove the host - proxy "
                              "link in Zabbix."))
    parser.add_argument("-j", "--journal", action="store_true",
                        help="Create journal entries in Netbox at write actions")
    return parser
