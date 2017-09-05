from polyglot.nodeserver_api import Node
import time
import random
import errno
from socket import error as socket_error
from copy import deepcopy

#Import classes from flux_led project:
import flux_led

# Changing these will not update the ISY names and labels, you will have to edit the profile.
COLORS = {
	0: ['RED', [255,0,0]],
	1: ['ORANGE', [255,165,0]],
	2: ['YELLOW', [255,255,0]],
	3: ['GREEN', [0,255,0]],
	4: ['CYAN', [0,255,255]],
	5: ['BLUE', [0,0,255]],
	6: ['PURPLE', [160,32,240]],
	7: ['PINK', [255,192,203]],
	8: ['WHITE', [255,255,255]],
	9: ['COLD_WHTE', [201,226,255]],
	10: ['WARM_WHITE', [255,147,41]],
	11: ['GOLD', [255,215,0]]
}

def myfloat(value, prec=1):
    """ round and return float """
    return round(float(value), prec)

class MagicHome(Node):

    def __init__(self, *args, **kwargs):
        self.flux_led_connector = flux_led
        self.scanner = self.flux_led_connector.BulbScanner()
        super(MagicHome, self).__init__(*args, **kwargs)

    def discover(self, *args, **kwargs):
        manifest = self.parent.config.get('manifest', {})
        self.scanner.scan(timeout=3)
        devices = self.scanner.getBulbInfo()
        self.logger.info('%i bulbs found. Checking status and adding to ISY', len(devices))
        for d in devices:
            led =flux_led.WifiLedBulb(d['ipaddr'],d['id'],d['model'])
            name = name = 'mh ' + str(led.ipaddr).replace('.',' ')
            address = str(led.macaddr).lower()
            lnode = self.parent.get_node(address)
            if not lnode:
                self.logger.info('Adding new MagicHome LED: %s(%s)', name, address)
                self.parent.bulbs.append(MagicHomeLED(self.parent, self.parent.get_node('magichome'), address, name, led, manifest))
        self.parent.long_poll()
        return True

    def query(self, **kwargs):
        self.parent.report_drivers()
        return True

    _drivers = {}

    _commands = {'DISCOVER': discover}
    
    node_def_id = 'magichome'

class MagicHomeLED(Node):
    
    def __init__(self, parent, primary, address, name, device, manifest=None):
        self.parent = parent
        self.address = address
        self.name = name
        self.device = device
        self.label = self.device.model
        self.connected = self.device.connected
        self.power = self.device.power
        self.color = list(self.device.color)
        self.tries = 0
        self.uptime = 0
        self.lastupdate = None
        self.updating = False
        super(MagicHomeLED, self).__init__(parent, address, self.name, primary, manifest)
        self.query()
        
    def update_info(self):
        if self.updating == True: return
        self.updating = True
        try:
            self.device.refreshState()
            self.connected = True
            self.power = self.device.power
            self.color = list(self.device.color)
            self.set_driver('GV4', self.connected)
            for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                self.set_driver(driver, self.color[ind])
            self.set_driver('ST', self.power)  
            self.tries = 0
        except Exception, ex:
            self.tries += 1
            if self.lastupdate == None:
                self.logger.error('Connection Error on %s initial MagicHome refreshState. %s', self.name, str(ex))
            elif self.tries == 3:
                self.device.disconnect() 
                self.logger.error('%i Connection Errors to %s, attempting to close and re-open connection', self.name)
            elif self.tries == 4:
                self.device.connect() #The connection with these LED's seems very spotty, try reconnecting if it has been down for a while.
            elif time.time() - self.lastupdate >= 60:
                self.logger.error('During Query, %s wasn\'t found. Marking as offline and attempting to re-connect', self.name)
                self.connected = False
                self.set_driver('GV4', self.connected)
                self.device.connect()
                self.uptime = 0
                self.tries = 0
            else:
                self.logger.error('Connection Error on %s MagicHome refreshState. This happens from time to time, normally safe to ignore. %s', self.name, str(ex))
        else:
            self.updating = False
            self.lastupdate = time.time()
            return True
        self.updating = False

    def query(self, **kwargs):
        self.update_info()
        self.report_driver()
        return True

    def _set_brightness(self, **kwargs):
        if self.updating == True: return
        self.updating = True
        value = kwargs.get("value")
        if value is not None:
            value = int(value / 100. * 255)
            if value > 0:
                current_max = max(self.color)
                try:
                    self.color[0] = int(self.color[0]*value/current_max) #RED
                    self.color[1] = int(self.color[1]*value/current_max) #GREEN
                    self.color[2] = int(self.color[2]*value/current_max) #BLUE
                    self.device.setRGB(self.color[0],self.color[1],self.color[2])
                    self.device.turnOn()
                except: pass
                self.logger.info('Received SetBrightness command from ISY. Changing %s brightness to: %i', self.name, value)
                for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                    self.set_driver(driver, self.color[ind])
                self.set_driver('ST', self.power)
            else:
                try:
                    self.device.turnOff()
                except: pass
                self.logger.info('Received SetBrightness command from ISY of 0, turning off %s.', self.name)
        else:
            try:
                self.device.turnOn()
            except: pass
            self.logger.info('Received SetBrightness command from ISY. No value specified, turning on %s.', self.name)
        self.updating = False
        return True

    def _seton(self, **kwargs):
        if self.updating == True: return
        self.updating = True
        _value = kwargs.get("value")
        if _value is not None:
            self._set_brightness(value=_value)
        else:
            try:
                self.device.turnOn()
            except: pass
        self.updating = False
        return True
        
    def _setoff(self, **kwargs):
        if self.updating == True: return
        self.updating = True
        try:
            self.device.turnOff()
        except: pass
        self.updating = False
        return True

    def _apply(self, **kwargs):
        self.logger.info('Received apply command: %s', str(kwargs))
        return True
        
    def _setcolor(self, **kwargs): 
        if self.updating == True: return True
        self.updating = True
        if self.connected:
            _color = int(kwargs.get('value'))
            try:
                #Scale the RGB values of the specified color based on the current brightness of the bulb:
                pct_brightness = max(self.color) / 255
                self.color[0] = int(COLORS[_color][1][0]*pct_brightness) #RED
                self.color[1] = int(COLORS[_color][1][1]*pct_brightness) #GREEN
                self.color[2] = int(COLORS[_color][1][2]*pct_brightness) #BLUE
                self.device.setRGB(self.color[0],self.color[1],self.color[2])
            except: pass
            self.logger.info('Received SetColor command from ISY. Changing %s color to: %s', self.name, COLORS[_color][0])
            for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                self.set_driver(driver, self.color[ind])
            self.set_driver('ST', self.power)
        else: 
            self.set_driver('GV4', self.connected)
            self.logger.info('Received SetColor, however %s is in a disconnected state... ignoring', self.name)
        self.updating = False
        return True
        
    def _setmanual(self, **kwargs): 
        if self.updating == True: return True
        self.updating = True
        if self.connected:
            _cmd = kwargs.get('cmd')
            _val = int(kwargs.get('value'))
            if _cmd == 'SETR': self.color[0] = _val
            if _cmd == 'SETG': self.color[1] = _val
            if _cmd == 'SETB': self.color[2] = _val
            try:
                self.device.setRGB(self.color[0],self.color[1],self.color[2])
            except: pass
            self.logger.info('Received manual change, updating the %s color to: %s', self.name, str(self.color))
            for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                self.set_driver(driver, self.color[ind])
            self.set_driver('ST', self.power)
        else: 
            self.set_driver('GV4', self.connected)
            self.logger.info('Received manual change, however %s is in a disconnected state... ignoring', self.name)
        self.updating = False
        return True

    def _setrgb(self, **kwargs):
        if self.updating == True: return True
        self.updating = True
        if self.connected:
            try:
                self.color = [int(kwargs.get('R.uom100')), int(kwargs.get('G.uom100')), int(kwargs.get('B.uom100'))]
            except TypeError:
                self.duration = 0
            try:
                self.device.setRGB(self.color[0],self.color[1],self.color[2])
            except: pass
            self.logger.info('Received manual change, updating the LED to: %s', str(self.color))
            for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                self.set_driver(driver, self.color[ind])
            self.set_driver('ST', self.power)
        else: 
            self.set_driver('GV4', self.connected)
            self.logger.info('Received manual change, however %s is in a disconnected state... ignoring', self.name)
        self.updating = False
        return True

    def _brt(self, **kwargs):
        if self.updating == True: return True
        self.updating = True
        if self.connected:
            brightness = int(max(self.color) / 255 * 100)
            new_brightness = min(100,max(0,brightness + 3))
            self._set_brightness(value=new_brightness)
            self.logger.info('Received brighten command, updating %s to: %i', self.name, new_brightness)
            for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                self.set_driver(driver, self.color[ind])
            self.set_driver('ST', self.power)
        else:
            self.set_driver('GV4', self.connected)
            self.logger.info('Received manual change, however %s is in a disconnected state... ignoring', self.name)
        self.updating = False
        return True

    def _dim(self, **kwargs):
        if self.updating == True: return True
        self.updating = True
        if self.connected:
            brightness = int(max(self.color) / 255 * 100)
            new_brightness = min(100,max(0,brightness - 3))
            self._set_brightness(value=new_brightness)
            self.logger.info('Received brighten command, updating %s to: %i', self.name, new_brightness)
            for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
                self.set_driver(driver, self.color[ind])
            self.set_driver('ST', self.power)
        else:
            self.set_driver('GV4', self.connected)
            self.logger.info('Received manual change, however %s is in a disconnected state... ignoring', self.name)
        self.updating = False
        return True


    _drivers = {'ST': [0, 51, int], 'GV1': [0, 100, int], 'GV2': [0, 100, int],
                'GV3': [0, 100, int], 'GV4': [0, 2, int]}

    _commands = {'DON': _seton, 'DFON':_seton, 'DOF': _setoff, 'DFOF': _setoff, 
                 'QUERY': query, 'BRT': _brt, 'DIM': _dim, 'APPLY': _apply,
                 'SET_COLOR': _setcolor, 'SETR': _setmanual, 'SETG': _setmanual,
                 'SETB': _setmanual, 'SET_RGB': _setrgb}

    node_def_id = 'magichomeled'