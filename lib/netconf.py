import os
import re
import struct
import socket
import fileinput
import netifaces as ni
from subprocess import call
from utils import Utils

# Set Network Configuration \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\ #
class NetConf():
    
    # Initialize the class
    def __init__(self, utils):
        self.utils  = utils
    
        # Define the primary network configuration file
        if self.utils.sys_type == 'Linux':
            
            # CentOS Linux
            if self.utils.os_type['distro'] == 'CentOS':
                self.nconf = '/etc/sysconfig/network'
        
        # Windows instances
        if self.utils.sys_type == 'Windows':
            self.nconf = ''
    
    # Build the interface configuration file
    def _iface_init(self, device, ip, mask):
        self.utils.log.info('Generating network interface configuration file for: ' + device)
        
        # CentOS 6/5.x network interfaces
        if self.utils.os_type['distro'] == 'CentOS':
            iface_conf = ("DEVICE=" + device + "\n"
                          "NAME=" + device + "\n"
                          "TYPE=Ethernet\n"
                          "ONBOOT=yes\n"
                          "BOOTPROTO=none\n"
                          "IPADDR=" + ip + "\n"
                          "NETMASK=" + mask + "\n"
                          "USERCTL=no\n"
                          "MTU=1400\n"
                          "NM_CONTROLLED=no")
        else:
            self.utils.error(4, self.utils.os_type['distro'])   
        return iface_conf
    
    # Set the default gateway in the network configuration
    def _get_def_gw(self):
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue
                def_gw = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                self.utils.log.info('Discovered default gateway: ' + def_gw)
                return def_gw

    # Update the network configuration
    def update(self):
        self.utils.log.info('Using primary network configuration file: ' + self.nconf)
        if self.utils.sys_type == 'Linux':

            # Get information for both adapters
            ip_info ={'pub_addr': ni.ifaddresses(self.utils.if_pub)[2][0]['addr'],
                      'pub_mask': ni.ifaddresses(self.utils.if_pub)[2][0]['netmask'],
                      'priv_addr': ni.ifaddresses(self.utils.if_priv)[2][0]['addr'],
                      'priv_mask': ni.ifaddresses(self.utils.if_priv)[2][0]['netmask']}
            self.utils.log.info('Generating IP info dictionary: ' + str(ip_info))
            
            # Update CentOS networking
            if self.utils.os_type['distro'] == 'CentOS':
            
                # Set the hostname in '/etc/sysconfig/network'
                self.utils.log.info('Setting system hostname: '+ self.utils.meta_json['name'])
                nconf_fc = open(self.nconf, 'r+').read()
                nconf_rx = re.compile('(^HOSTNAME=).*$', re.MULTILINE)
                nconf_new = nconf_rx.sub(r'\g<1>' + self.utils.meta_json['name'], nconf_fc)
                open(self.nconf, 'w+').write(nconf_new)
                
                # Update '/proc/sys/kernel/hostname'
                cmd_string = "echo -n %s > /proc/sys/kernel/hostname" % (self.utils.meta_json['name'])
                os.system(cmd_string)
            
                # Write the default gateway to '/etc/sysconfig/network'
                ip_gateway = self._get_def_gw()
                self.utils.log.info('Setting default gateway: '+ ip_gateway)
                with open(self.nconf, 'a') as netconf:
                    netconf.write('GATEWAY=' + ip_gateway)
            
                # Build the interface files for each network
                iface_conf_pub  = self._iface_init(self.utils.if_pub, ip_info['pub_addr'], ip_info['pub_mask'])
                iface_conf_priv = self._iface_init(self.utils.if_priv, ip_info['priv_addr'], ip_info['priv_mask'])
            
                # Update the config files
                self.utils.log.info('Updating network interface configuration for: public = ' + self.utils.if_pub + ', private = ' + self.utils.if_priv)
                open('/etc/sysconfig/network-scripts/ifcfg-' + self.utils.if_pub, 'w').write(iface_conf_pub)
                open('/etc/sysconfig/network-scripts/ifcfg-' + self.utils.if_priv, 'w').write(iface_conf_priv)
            
                # Restart the networking service and return the IP information
                self.utils.log.info('Restarting network services')
                os.system('service network restart &> /dev/null')
            self.utils.ip_info = ip_info