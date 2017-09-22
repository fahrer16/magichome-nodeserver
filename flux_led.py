#!/usr/bin/env python

"""
Modified from https://github.com/beville/flux_led to work as a component of the MagicHome nodeserver for Polyglot
##### Available:
* Discovering bulbs on LAN
* Turning on/off bulb
* Get state information
* Setting "warm white" mode
* Setting single color mode
* Setting preset pattern mode
* Setting custom pattern mode
* Reading timers
* Setting timers
"""
import socket
import time
import sys
import datetime
from optparse import OptionParser,OptionGroup
import ast

class utils:
    @staticmethod
    def color_tuple_to_string(rgb):
        # try to convert to an english name
        try:
            return webcolors.rgb_to_name(rgb)
        except Exception as e:
            #print e
            pass
        return str(rgb)
    
    @staticmethod
    def get_color_names_list():
        names = set()
        for key in webcolors.css2_hex_to_names.keys():
            names.add(webcolors.css2_hex_to_names[key])
        for key in webcolors.css21_hex_to_names.keys():
            names.add(webcolors.css21_hex_to_names[key])
        for key in webcolors.css3_hex_to_names.keys():
            names.add(webcolors.css3_hex_to_names[key])
        for key in webcolors.html4_hex_to_names.keys():
            names.add(webcolors.html4_hex_to_names[key])			
        return sorted(names)
        
    @staticmethod
    def date_has_passed(dt):
        delta = dt - datetime.datetime.now()
        return delta.total_seconds() < 0

    #@staticmethod
    #def dump_bytes(bytes):
    #    print ''.join('{:02x} '.format(x) for x in bytearray(bytes))
    
    max_delay = 0x1f
    
    @staticmethod
    def delayToSpeed(delay):
        # speed is 0-100, delay is 1-31
        # 1st translate delay to 0-30
        delay = delay -1
        if delay > utils.max_delay - 1 :
            delay = utils.max_delay - 1
        if delay < 0: 
            delay = 0
        inv_speed = int((delay * 100)/(utils.max_delay - 1))
        speed =  100-inv_speed
        return speed
    
    @staticmethod
    def speedToDelay(speed):
        # speed is 0-100, delay is 1-31		
        if speed > 100:
            speed = 100
        if speed < 0:
            speed = 0
        inv_speed = 100-speed
        delay = int((inv_speed * (utils.max_delay-1))/100)
        # translate from 0-30 to 1-31
        delay = delay + 1
        return delay
    
    @staticmethod
    def byteToPercent(byte):
        if byte > 255:
            byte = 255
        if byte < 0:
            byte = 0
        return int((byte * 100)/255)

    @staticmethod
    def percentToByte(percent):
        if percent > 100:
            percent = 100
        if percent < 0:
            percent = 0
        return int((percent * 255)/100)

class PresetPattern:
	seven_color_cross_fade =   0x25
	red_gradual_change =       0x26
	green_gradual_change =     0x27
	blue_gradual_change =      0x28
	yellow_gradual_change =    0x29
	cyan_gradual_change =      0x2a
	purple_gradual_change =    0x2b
	white_gradual_change =     0x2c
	red_green_cross_fade =     0x2d
	red_blue_cross_fade =      0x2e
	green_blue_cross_fade =    0x2f
	seven_color_strobe_flash = 0x30
	red_strobe_flash =         0x31
	green_strobe_flash =       0x32
	blue_stobe_flash =         0x33
	yellow_strobe_flash =      0x34
	cyan_strobe_flash =        0x35
	purple_strobe_flash =      0x36
	white_strobe_flash =       0x37
	seven_color_jumping =      0x38
	
	@staticmethod
	def valid(pattern):
		if pattern < 0x25 or pattern > 0x38:
			return False
		return True
	
	@staticmethod
	def valtostr(pattern):
		for key, value in PresetPattern.__dict__.iteritems():
			if type(value) is int and value == pattern:
				return key.replace("_", " ").title()
		return None

class LedTimer():
	Mo = 0x02
	Tu = 0x04
	We = 0x08  
	Th = 0x10 
	Fr = 0x20
	Sa = 0x40 
	Su = 0x80
	Everyday = Mo|Tu|We|Th|Fr|Sa|Su
	Weekdays = Mo|Tu|We|Th|Fr
	Weekend = Sa|Su

	@staticmethod
	def dayMaskToStr(mask):
		for key, value in LedTimer.__dict__.iteritems():
			if type(value) is int and value == mask:
				return key
		return None  

	def __init__(self, bytes=None):
		if bytes is not None:
			self.fromBytes(bytes)
			return
			
		the_time = datetime.datetime.now() + datetime.timedelta(hours=1)  
		self.setTime(the_time.hour, the_time.minute)
		self.setDate(the_time.year, the_time.month, the_time.day)
		self.setModeTurnOff()
		self.setActive(False)
		
	def setActive(self, active=True):
		self.active = active
		
	def isActive(self):
		return self.active

	def isExpired(self):
		# if no repeat mask and datetime is in past, return True
		if self.repeat_mask != 0:
			return False
		elif self.year!=0 and self.month!=0 and self.day!=0:
			dt = datetime.datetime(self.year, self.month, self.day, self.hour, self.minute)
			if  utils.date_has_passed(dt):
				return True
		return False
		
	def setTime(self, hour, minute):
		self.hour = hour
		self.minute = minute

	def setDate(self, year, month, day):
		self.year = year
		self.month = month		
		self.day = day
		self.repeat_mask = 0

	def setRepeatMask(self, repeat_mask):
		self.year = 0		
		self.month = 0		
		self.day = 0
		self.repeat_mask = repeat_mask

	def setModeDefault(self):
		self.mode = "default"
		self.pattern_code = 0
		self.turn_on = True
		self.red = 0
		self.green = 0
		self.blue = 0
		self.warmth_level = 0
		
	def setModePresetPattern(self, pattern, speed):
		self.mode = "preset"
		self.warmth_level = 0
		self.pattern_code = pattern
		self.delay = utils.speedToDelay(speed)
		self.turn_on = True
		
	def setModeColor(self, r, g, b):
		self.mode = "color"
		self.warmth_level = 0
		self.red = r
		self.green = g
		self.blue = b		
		self.pattern_code = 0x61
		self.turn_on = True

	def setModeWarmWhite(self, level):
		self.mode = "ww"
		self.warmth_level = utils.percentToByte(level)
		self.pattern_code = 0x61
		self.red = 0
		self.green = 0
		self.blue = 0
		self.turn_on = True

	def setModeTurnOff(self):
		self.mode = "off"
		self.turn_on = False
		self.pattern_code = 0
	
	"""
	timer are in six 14-byte structs
		f0 0f 08 10 10 15 00 00 25 1f 00 00 00 f0 0f
		 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14
		0: f0 when active entry/ 0f when not active
		1: (0f=15) year when no repeat, else 0
		2:  month when no repeat, else 0
		3:  dayofmonth when no repeat, else 0
		4: hour
		5: min
		6: 0
		7: repeat mask, Mo=0x2,Tu=0x04, We 0x8, Th=0x10 Fr=0x20, Sa=0x40, Su=0x80
		8:  61 for solid color or warm, or preset pattern code
		9:  r (or delay for preset pattern)
		10: g
		11: b
		12: warm white level
		13: 0f = off, f0 = on ?
	"""		
	def fromBytes(self, bytes):
		#utils.dump_bytes(bytes)
		self.red = 0
		self.green = 0
		self.blue = 0		
		if bytes[0] == 0xf0:
			self.active = True
		else:
			self.active = False
		self.year = bytes[1]+2000
		self.month = bytes[2]
		self.day = bytes[3]
		self.hour = bytes[4]
		self.minute = bytes[5]
		self.repeat_mask = bytes[7]
		self.pattern_code = bytes[8]
	
		if self.pattern_code == 0x61:
			self.mode = "color"
			self.red = bytes[9]
			self.green = bytes[10]
			self.blue = bytes[11]
		elif self.pattern_code == 0x00:
			self.mode ="default"
		else:
			self.mode = "preset"
			self.delay = bytes[9] #same byte as red

		self.warmth_level = bytes[12]
		if self.warmth_level != 0:
			self.mode = "ww"
			
		if bytes[13] == 0xf0:
			self.turn_on = True
		else:
			self.turn_on = False
			self.mode = "off"

	def toBytes(self):
		bytes = bytearray(14)
		if not self.active:
			bytes[0] = 0x0f
			# quit since all other zeros is good
			return bytes
				
		bytes[0] = 0xf0
		
		if self.year >= 2000:
			bytes[1] =  self.year - 2000
		else:
			bytes[1] = self.year			
		bytes[2] = self.month
		bytes[3] = self.day
		bytes[4] = self.hour
		bytes[5] = self.minute
		# what is 6?
		bytes[7] = self.repeat_mask
		
		if not self.turn_on:
			bytes[13] = 0x0f
			return bytes		
		bytes[13] = 0xf0
		
		bytes[8] = self.pattern_code
		if self.mode == "preset":	
			bytes[9] = self.delay
			bytes[10] = 0
			bytes[11] = 0
		else:
			bytes[9] = self.red
			bytes[10] = self.green
			bytes[11] = self.blue
		bytes[12] = self.warmth_level

		return bytes
			
	def __str__(self):
		txt = ""
		if not self.active:
		  return "Unset"
		
		if self.turn_on:
			txt += "[ON ]"
		else:
			txt += "[OFF]"

		txt += " "

		txt += "{:02}:{:02}  ".format(self.hour,self.minute)
	
		if self.repeat_mask == 0:
			txt += "Once: {:04}-{:02}-{:02}".format(self.year,self.month,self.day)
		else:
			bits = [LedTimer.Su,LedTimer.Mo,LedTimer.Tu,LedTimer.We,LedTimer.Th,LedTimer.Fr,LedTimer.Sa]
			for b in bits:
				if self.repeat_mask & b:
					txt += LedTimer.dayMaskToStr(b)
				else:
					txt += "--"
			txt += "  "
				
		txt += "  "
		if self.pattern_code == 0x61:
			if self.warmth_level != 0:
				txt += "Warm White: {}%".format(utils.byteToPercent(self.warmth_level))
			else:
				color_str = utils.color_tuple_to_string((self.red,self.green,self.blue))
				txt += "Color: {}".format(color_str)

		elif PresetPattern.valid(self.pattern_code):
			pat = PresetPattern.valtostr(self.pattern_code)
			speed = utils.delayToSpeed(self.delay)
			txt += "{} (Speed:{}%)".format(pat, speed)
			
		return txt

class WifiLedBulb():
    def __init__(self, ipaddr, macaddr, model="",port=5577):
        self.ipaddr = ipaddr
        self.port = port
        self.__isOn = False
        self.color = [0,0,0]
        self.power = 0
        self.macaddr = macaddr
        self.model = model
        self.connected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect()
        self.__state_str = ""
        self.refreshState()

    def connect(self):
        try:
            self.socket.connect((self.ipaddr, self.port))
            self.connected = True
        except:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except: pass
            self.connected = False

    def disconnect(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
            self.connected = False
        except: pass
        
    def __determineMode(self, ww_level, pattern_code):
        mode = "unknown"
        if pattern_code in [ 0x61, 0x62]:
            if ww_level != 0:
                mode = "ww"
            else:
                mode = "color"
        elif pattern_code == 0x60:
            mode = "custom"
        elif PresetPattern.valid(pattern_code):
            mode = "preset"
        return mode

    def __updatePower(self):
        if self.__isOn:
            self.power = min(max(int(max(self.color) / 255. * 100.),0),100)
        else:
            self.power = 0

    def refreshState(self):
        msg = bytearray([0x81, 0x8a, 0x8b])
        try:
            self.__write(msg)
            rx = self.__readResponse(14)
        except:
            self.connect()
            return False

        power_state = rx[2]
        power_str = "Unknown power state"

        if power_state == 0x23:
            self.__isOn = True
            power_str = "ON "
        elif power_state == 0x24:
            self.__isOn = False
            power_str = "OFF"
            
        pattern = rx[3]
        ww_level = rx[9]
        mode = self.__determineMode(ww_level, pattern)
        delay = rx[5]
        speed = utils.delayToSpeed(delay)
        
        if mode == "color":
            self.color = [rx[6],rx[7],rx[8]]
            self.__updatePower()
            color_str = utils.color_tuple_to_string((rx[6],rx[7],rx[8]))
            mode_str = "Color: {}".format(color_str)
        elif mode == "ww":
            self.color = [0,0,0]
            if self.__isOn:
                self.power = int(rx[9]/255*100)
            else:
                self.power = 0
            mode_str = "Warm White: {}%".format(utils.byteToPercent(ww_level))
            #not yet implemented for polyglot interface for ISY (future enhancement)
        elif mode == "preset":
            pat = PresetPattern.valtostr(pattern)
            mode_str = "Pattern: {} (Speed {}%)".format(pat, speed)
            #not yet implemented for polyglot interface for ISY (future enhancement)
        elif mode == "custom":
            mode_str = "Custom pattern (Speed {}%)".format(speed)
            #not yet implemented for polyglot interface for ISY (future enhancement)
        else:
            mode_str = "Unknown mode 0x{:x}".format(pattern)
        if pattern == 0x62:
            mode_str += " (tmp)"
        self.__state_str = "{} [{}]".format(power_str, mode_str)
        return True

    def __str__(self):
        return self.__state_str

            
    def getClock(self):
        msg = bytearray([0x11, 0x1a, 0x1b, 0x0f])
        self.__write(msg)
        rx = self.__readResponse(12)
        #self.dump_data(rx)
        year =  rx[3] + 2000
        month = rx[4]
        date = rx[5]
        hour = rx[6]
        minute = rx[7]
        second = rx[8]
        #dayofweek = rx[9]
        try:
            dt = datetime.datetime(year,month,date,hour,minute,second)
        except:
            dt = None
        return dt

    def setClock(self):
        msg = bytearray([0x10, 0x14])
        now = datetime.datetime.now()
        msg.append(now.year-2000)
        msg.append(now.month)
        msg.append(now.day)
        msg.append(now.hour)
        msg.append(now.minute)
        msg.append(now.second)
        msg.append(now.isoweekday()) # day of week
        msg.append(0x00)
        msg.append(0x0f)
        self.__write(msg)

    def turnOn(self, on=True):
        if on:
            msg = bytearray([0x71, 0x23, 0x0f, 0xa3])
        else:
            msg = bytearray([0x71, 0x24, 0x0f, 0xa4])
            
        self.__write(msg)
        #print "set bulb {}".format(on)
        #time.sleep(.5)
        #x = self.__readResponse(4)
        self.__isOn = on
        self.__updatePower()
         
    def turnOff(self):
        msg = bytearray([0x71, 0x24, 0x0f, 0xa4])
        self.__write(msg)
        self.power = 0
    
    def setWarmWhite(self, level, persist=True):
        if persist:
            msg = bytearray([0x31])
        else:
            msg = bytearray([0x41])
        msg.append(0x00)
        msg.append(0x00)
        msg.append(0x00)
        msg.append(utils.percentToByte(level))
        msg.append(0x0f)
        msg.append(0x0f)
        self.__write(msg)
        
    def setRGB(self, r,g,b, persist=True):
        if persist:
            msg = bytearray([0x31])
        else:
            msg = bytearray([0x41])
        msg.append(r)
        msg.append(g)
        msg.append(b)
        msg.append(0x00) #Warm White Value
        msg.append(0x00) #Cool White Value
        msg.append(0x0f) #FALSE (don't use white value)
        self.__write(msg)
        self.color = [r,g,b]
        self.__updatePower()

    def setPresetPattern(self, pattern, speed):

        PresetPattern.valtostr(pattern)
        if not PresetPattern.valid(pattern):
            #print "Pattern must be between 0x25 and 0x38"
            raise Exception

        delay = utils.speedToDelay(speed)
        #print "speed {}, delay 0x{:02x}".format(speed,delay)
        pattern_set_msg = bytearray([0x61])
        pattern_set_msg.append(pattern)
        pattern_set_msg.append(delay)
        pattern_set_msg.append(0x0f)

        self.__write(pattern_set_msg)

    def getTimers(self):
        msg = bytearray([0x22, 0x2a, 0x2b, 0x0f])
        self.__write(msg)
        resp_len = 88
        rx = self.__readResponse(resp_len)
        if len(rx) != resp_len:
            print "response too short!"
            raise Exception
            
        #utils.dump_data(rx)
        start = 2
        timer_list = []
        #pass in the 14-byte timer structs 
        for i in range(6):
          timer_bytes = rx[start:][:14]
          timer = LedTimer(timer_bytes)
          timer_list.append(timer)
          start += 14
          
        return timer_list
                
    def sendTimers(self, timer_list):
        # remove inactive or expired timers from list
        for t in timer_list:
            if not t.isActive() or t.isExpired():
                timer_list.remove(t)
                
        # truncate if more than 6
        if len(timer_list) > 6:
            print "too many timers, truncating list"
            del timer_list[6:]
            
        # pad list to 6 with inactive timers
        if len(timer_list) != 6:
            for i in range(6-len(timer_list)):
                timer_list.append(LedTimer())
        
        msg_start = bytearray([0x21])
        msg_end = bytearray([0x00, 0xf0])
        msg = bytearray()
        
        # build message
        msg.extend(msg_start)
        for t in timer_list:
            msg.extend(t.toBytes())
        msg.extend(msg_end)
        self.__write(msg)
        
        # not sure what the resp is, prob some sort of ack?
        rx = self.__readResponse(1)
        rx = self.__readResponse(3)
        
    def setCustomPattern(self, rgb_list, speed, transition_type):
                
        # truncate if more than 16
        if len(rgb_list) > 16:
            print "too many colors, truncating list"
            del rgb_list[16:]
            
        # quit if too few
        if len(rgb_list) == 0:
            print "no colors, aborting"
            return
        
        msg = bytearray()
        
        first_color = True
        for rgb in rgb_list:
            if first_color:
                lead_byte = 0x51
                first_color = False
            else:
                lead_byte = 0
            r,g,b = rgb
            msg.extend(bytearray([lead_byte, r,g,b]))
        
        # pad out empty slots
        if len(rgb_list) != 16:
            for i in range(16-len(rgb_list)):
                msg.extend(bytearray([0, 1, 2, 3]))
                
        msg.append(0x00)
        msg.append(utils.speedToDelay(speed))
        
        if transition_type =="gradual":
            msg.append(0x3a)
        elif transition_type =="jump":
            msg.append(0x3b)
        elif transition_type =="strobe":
            msg.append(0x3c)
        else:
            #unknown transition string: using 'gradual'
            msg.append(0x3a)
        msg.append(0xff)
        msg.append(0x0f)

        self.__write(msg)

    def __writeRaw(self, bytes):
        try:
            self.socket.send(bytes)
        except:
            try:
                self.socket.connect((self.ipaddr, self.port))
                self.socket.send(bytes)
            except: pass #communication with these MagicHome LED Controllers can be spotty, unfortunately.  Need to add some better error handling, this is temporary to get up and running

    def __write(self, bytes):
        # calculate checksum of byte array and add to end
        csum = sum(bytes) & 0xFF
        bytes.append(csum)
        #print "-------------",utils.dump_bytes(bytes)
        self.__writeRaw(bytes)
        #time.sleep(.4)		
        
    def __readResponse(self, expected):
        remaining = expected
        rx = bytearray()
        while remaining > 0:
            chunk = self.__readRaw(remaining)
            remaining -= len(chunk)
            rx.extend(chunk)
        return rx
            
    def __readRaw(self, byte_count=1024):
        try:
            rx = self.socket.recv(byte_count)
            return rx
        except: pass
    
class BulbScanner():
    def __init__(self):
        self.found_bulbs = []
    
    def getBulbInfoByID(self, id):
        bulb_info = None
        for b in self.found_bulbs:
            if b['id'] == id:
                return b
        return b		

    def getBulbInfo(self):
        return self.found_bulbs	
    
    def scan(self, timeout=10):
        
        DISCOVERY_PORT = 48899
    
        sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.bind(('', DISCOVERY_PORT))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        msg = "HF-A11ASSISTHREAD"
        
        # set the time at which we will quit the search
        quit_time = time.time() + timeout

        response_list = []
        # outer loop for query send
        while True:
            if time.time() > quit_time:
                break			
            # send out a broadcast query
            sock.sendto(msg, ('<broadcast>', DISCOVERY_PORT))
            
            # inner loop waiting for responses
            while True:
                
                sock.settimeout(1)
                try:
                    data, addr = sock.recvfrom(64)
                except socket.timeout:
                    data = None
                    if time.time() > quit_time:
                        break
    
                if data is not None and data != msg:
                    # tuples of IDs and IP addresses
                    item = dict()
                    item['ipaddr'] = data.split(',')[0]
                    item['id'] = data.split(',')[1]
                    item['model'] = data.split(',')[2]
                    response_list.append(item)

        self.found_bulbs = response_list
        return response_list
#=========================================================================