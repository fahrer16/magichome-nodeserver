# MagicHome-polyglot
This is the MagicHome Node Server for the ISY Polyglot interface.  
(c) fahrer16 aka Brian Feeney.  
MIT license. 

I built this on Ubuntu 17.04 for ISY version 5.0.10 and polyglot version 0.0.7 from https://github.com/UniversalDevicesInc/Polyglot

This is my first attempt at building a node server for the ISY using Polyglot and I borrowed heavily from Einstein42's lifx-nodeserver (https://github.com/Einstein42/lifx-nodeserver) and beville's flux_led project (https://github.com/beville/flux_led)

There are quite a few very inexpensive LED controllers that share the very simple TCP protocol used in the "MagicHome" app (https://play.google.com/store/apps/details?id=com.Zengge.LEDWifiMagicHome&hl=en).
So far, this node server only implements the basic controls necessary to control RGB LED's without any of the modes/presets available in the App.  Since I don't currently ahve an Warm White LED's, that portion of the protocol isn't currently implemented here.  The code is present in beville's flux_led project, so it would be relatively easy to implement it if anyone is interested.


# Installation Instructions:
Same as most other ISY node servers:

1. Backup ISY (just in case)
2. Clone the MagicHome Node Server into the /config/node_servers folder of your Polyglot installation:
  * `cd Polyglot/config/node_servers
  * `git clone https://github.com/fahrer16/magichome-nodeserver.git
3. Add Node Server into Polyglot instance.
  * Log into polyglot web page (http://ip:8080)
  * Select "Add Node Server" and select the following options:
    * Node Server Type: MagicHome
    * Name: Up to you, I've only used "MagicHome"
    * Node Server ID: Any available slot on the ISY Node Servers/Configure menu from the administration console
  * Click "ADD" and the new node server should appear on the left and hopefully say "Running" under it
  * Open the new node server by clicking on it
  * Copy the "Base URL" and download the profile for the next step
4. Add Node Server into ISY:
  * Log into the ISY admin console and navigate to "Network Connections" on the empty node server slot you entered into Polyglot earlier:
    * Profile Name: Again, up to you, but it's easiest to keep track if it's the same name entered for the node server in Polyglot
    * User ID / Password: Polyglot credentials
    * Base URL: Paste Base URL copied earlier from Polyglot node server web page
    * Host Name: Host Name (or IP address) of your Polyglot server
    * Port: Default is 8080
  * Upload the profile downloaded from the Polyglot node server web page earlier
5. Click "Ok" and reboot the ISY (Configuration tab then "Reboot")
6. Once the ISY is back up upload the profile again in the node server network configuration and reboot the ISY again (quirk of the ISY according to others' node installation instructions)
7. Log back into the ISY admin console.  If your new nodes aren't present, "Add All Nodes" from the new node server from the "Node Servers" menu.

The LED controllers should show the correct status now, hit "Query" if the status fields are empty.  The connection to the LED controllers drops out frequently for me (maybe my network or WiFi setup, maybe my code is flaky).  I've noticed using the MagicHome app while the node server is connected to the controllers causes the node server to lose connection.  I've tried adding some code to close the connection and re-connect periodically but I've found it reliable as long as I don't use anything else to control the LED's
 
  