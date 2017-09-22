#!/usr/bin/python
""" MagicHome/LEDENET Node Server for Polyglot by B. Feeney (fahrer@gmail.com).  
    Based on LIFX Node Server for Polyglot by Einstein.42(James Milne) (https://github.com/Einstein42/lifx-nodeserver) 
    Also Based on utility for controlling Flux WiFi Smart LED Light Bulbs by beville (https://github.com/beville/flux_led)"""

from polyglot.nodeserver_api import NodeServer, SimpleNodeServer, Node
from polyglot.nodeserver_api import PolyglotConnector

from polyMagicHome_types import MagicHome

# Test for PyYaml config file.
#import yaml

VERSION = "0.0.1"

class MagicHomeNodeServer(SimpleNodeServer):
    """ Magic Home Node Server """
    controller = []
    bulbs = []

    def setup(self):
        self.logger = self.poly.logger
        #self.logger.info('Config File param: %s', self.poly.configfile)
        manifest = self.config.get('manifest', {})
        self.controller = MagicHome(self, 'magichome', 'MagicHome Bridge', True, manifest)
        self.controller.discover()
        self.update_config()

    def poll(self):
        if len(self.bulbs) >= 1:
            for i in self.bulbs:
                i.update_drivers() #only reports currently tracked values without querying the device

    def long_poll(self):
        if len(self.bulbs) >= 1:
            for i in self.bulbs:
                i.update_info() #queries the device then reports the updated values

    def report_drivers(self):
        if len(self.bulbs) >= 1:
            for i in self.bulbs:
                i.report_driver()

def main():
    # Setup connection, node server, and nodes
    poly = PolyglotConnector()
    # Override shortpoll and longpoll timers to 5/30, once per second is unnessesary
    nserver = MagicHomeNodeServer(poly, 5, 30)
    poly.connect()
    poly.wait_for_config()
    poly.logger.info("MagicHome Node Server Interface version " + VERSION + " created. Initiating setup.")
    nserver.setup()
    poly.logger.info("Setup completed. Running Server.")
    nserver.run()

if __name__ == "__main__":
    main()
