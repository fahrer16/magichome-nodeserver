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
        self.device = device
        self.name = name
        self.address = address
        self.label = self.device.model
        self.updating = False
        super(MagicHomeLED, self).__init__(parent, address, name, primary, manifest)
        self.query()
        
    def update_info(self):
        self.updating = True
        try:
            self.device.refreshState()
        except Exception, ex:
            self.logger.error('Connection Error on %s MagicHome refreshState. This happens from time to time, normally safe to ignore. %s', self.name, str(ex))
            return False
        else:
            self.update_drivers()
            self.updating = False
            return True

    def query(self, **kwargs):
        self.update_info()
        self.report_driver()
        return True

    def _st(self, **kwargs):
        self.update_info()
        self.report_driver()
        return True

    def _set_brightness(self, value=None, **kwargs):
        if self.updating == True: return
        self.updating = True
        if value is not None:
            _value = int(value / 100. * 255)
            if _value > 0:
                current_max = float(max(self.device.color))
                try:
                    _red = int((self.device.color[0] / current_max) * _value ) #RED
                    _green = int((self.device.color[1] / current_max) *_value) #GREEN
                    _blue = int((self.device.color[2] / current_max) *_value) #BLUE
                    self.device.setRGB(_red,_green,_blue)
                    self.device.turnOn()
                    self.logger.info('Received SetBrightness command from ISY. Changing %s brightness to: %i', self.name, _value)
                except Exception, ex: 
                    self.logger.error('Error seting brightness on %s to %i. %s', self.name, _value, str(ex))
            else:
                try:
                    self.device.turnOff()
                    self.power = self.device.power
                    self.logger.info('Received SetBrightness command from ISY of 0, turning off %s.', self.name)
                except Exception, ex: 
                    self.logger.error('Error turning off %s (set brightness to 0). %s', self.name, str(ex))
        else:
            try:
                self.device.turnOn()
                self.power = self.device.power
                self.logger.info('Received SetBrightness command from ISY. No value specified, turning on %s.', self.name)
            except Exception, ex: 
                self.logger.error('Error turning on %s (set brightness to 100). %s', self.name, str(ex))
        self.updating = False
        self.update_drivers()
        return True

    def _seton(self, **kwargs):
        if self.updating == True: return
        _value = kwargs.get('value')
        if _value is not None:
            self._set_brightness(value=_value)
        else:
            self.updating = True
            try:
                self.device.turnOn()
                self.update_drivers()
            except Exception, ex: 
                self.logger.error('Error turning on %s. %s', self.name, str(ex))
        self.updating = False
        return True
        
    def _setoff(self, **kwargs):
        if self.updating == True: return
        self.updating = True
        try:
            self.device.turnOff()
            self.update_drivers()
        except Exception, ex: 
            self.logger.error('Error turning off %s. %s', self.name, str(ex))
        self.updating = False
        return True

    def _faston(self, **kwargs):
        _seton(value=100)
        return True

    def _apply(self, **kwargs):
        self.logger.info('Received apply command: %s', str(kwargs))
        return True
        
    def _setcolor(self, **kwargs): 
        if self.updating == True: return True
        self.updating = True
        _color = int(kwargs.get('value'))
        try:
            #Scale the RGB values of the specified color based on the current brightness of the bulb:
            pct_brightness = max(self.device.color) / 255.
            _red = int(COLORS[_color][1][0]*pct_brightness) #RED
            _green = int(COLORS[_color][1][1]*pct_brightness) #GREEN
            _blue = int(COLORS[_color][1][2]*pct_brightness) #BLUE
            self.device.setRGB(_red,_green,_blue)
            self.update_drivers()
            self.logger.info('Received SetColor command from ISY. Changing %s color to: %s', self.name, COLORS[_color][0])
        except Exception, ex: 
            self.logger.error('Error seting color on %s to %s. %s', self.name, str(_color), str(ex))
        self.updating = False
        return True
        
    def _setmanual(self, **kwargs): 
        if self.updating == True: return True
        self.updating = True
        _cmd = kwargs.get('cmd')
        _val = int(kwargs.get('value'))
        if _cmd == 'SETR': self.device.color[0] = _val
        if _cmd == 'SETG': self.device.color[1] = _val
        if _cmd == 'SETB': self.device.color[2] = _val
        try:
            self.device.setRGB(self.color[0],self.color[1],self.color[2])
            self.update_drivers()
            self.logger.info('Received manual change, updating %s to: %s', self.name, str(self.device.color))
        except Exception, ex: 
            self.logger.error('Error setting manual rgb on %s (cmd=%s, value=%s). %s', self.name, str(_cmd), str(_val), str(ex))
        self.updating = False
        return True

    def _setrgb(self, **kwargs):
        if self.updating == True: return True
        self.updating = True
        try:
            self.device.setRGB(int(kwargs.get('R.uom100')), int(kwargs.get('G.uom100')), int(kwargs.get('B.uom100')))
            self.update_drivers()
            self.logger.info('Received manual change, updating the LED to: %s', str(kwargs))
        except Exception, ex: 
            self.logger.error('Error setting rgb on %s to %s. %s', self.name, str(kwargs), str(ex))
        self.updating = False
        return True

    def _brt(self, **kwargs):
        if self.updating == True: return True
        _brightness = int(max(self.device.color) / 255 * 100.)
        _new_brightness = min(100,max(0,_brightness + 3))
        self._set_brightness(value=_new_brightness)
        self.logger.info('Received brighten command, updating %s to: %i', self.name, _new_brightness)
        return True

    def _dim(self, **kwargs):
        if self.updating == True: return True
        _brightness = int(max(self.device.color) / 255 * 100.)
        _new_brightness = min(100,max(0,_brightness - 3))
        self._set_brightness(value=_new_brightness)
        self.logger.info('Received brighten command, updating %s to: %i', self.name, _new_brightness)
        return True

    def update_drivers(self):
        self.set_driver('GV4', self.device.connected)
        for ind, driver in enumerate(('GV1', 'GV2', 'GV3')):
            self.set_driver(driver, self.device.color[ind])
        self.set_driver('ST', self.device.power)
        #self.report_driver()
        return True


    _drivers = {'ST': [0, 51, int], 'GV1': [0, 100, int], 'GV2': [0, 100, int],
                'GV3': [0, 100, int], 'GV4': [0, 2, int]}

    _commands = {'DON': _seton, 'DFON':_faston, 'DOF': _setoff, 'DFOF': _setoff, 'ST': _st,
                 'QUERY': query, 'BRT': _brt, 'DIM': _dim, 'APPLY': _apply,
                 'SET_COLOR': _setcolor, 'SETR': _setmanual, 'SETG': _setmanual,
                 'SETB': _setmanual, 'SET_RGB': _setrgb}

    node_def_id = 'magichomeled'