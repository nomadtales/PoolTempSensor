# Import required libraries
import network
import socket
import time
from time import sleep
import onewire
import ds18x20
import dht
import machine
import json
import variables # custom variables file

# DS sensors bytearrays
poolsensor = variables.poolsensor
pondsensor = variables.pondsensor

# setup internal temp and LED
adcpin = 4
inttemp = machine.ADC(adcpin)
intled = machine.Pin("LED", machine.Pin.OUT)

# setup ds18b20 sensor(s)
ds_pin = machine.Pin(22)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))

# setup DHT11 sensor
dht_pin = machine.Pin(21)
dht_sensor = dht.DHT11(dht_pin)

# check ds sensor exists
roms = ds_sensor.scan()
print('Found DS sensors: ', roms)

# check dht sensor exists
print('Found DHT sensors: ', dht_sensor)

# function for internal temp
def ReadPicoTemp():
    adc_value = inttemp.read_u16()
    volt = (3.3/65535) * adc_value
    temperature = 27 - (volt - 0.706)/0.001721
    return round(temperature, 1)

# function for ds18b20 sensor(s) temps
def ReadDS18b20Temp(sensor):
    err = None
    temp = None
    try:
        # convert temp
        ds_sensor.convert_temp()
        # pause
        time.sleep_ms(750)
        # get temp
        temp = ds_sensor.read_temp(sensor)
        # pause
        time.sleep_ms(750)
    except Exception as err:
        print('Failed reading DS sensor: ', sensor)
        temp = None
    return temp

def ReadDHTSensor():
    try:
        # get sensor reading
        dht_sensor.measure()
        #create dictionary
        dht_read = {
            "temp": dht_sensor.temperature(),
            "humidity": dht_sensor.humidity()
        }
        # pause
        time.sleep_ms(750)
    except Exception as err:
        print('Failed reading DHT sensor')
        dht_read = {
            "temp": None,
            "humidity": None
        }
    return dht_read

def GetWLANStr(SSID):
    try:
        accessPoints = wlan.scan() 
        for ap in accessPoints:
            if ap[0] == bytes(SSID, 'utf-8'):
                strength = int((f'{ap[3]}'))
    except Exception as err:
        print('Error: ', err)
        strength = None
    return strength

# Indicate that the app started
intled.value(1)
sleep(3)
intled.value(0)

# setup WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# prevent the wireless chip from activating power-saving mode when it is idle
wlan.config(pm = 0xa11140) 

# Connect to your AP using your login details
wlan.connect(variables.SSID, variables.SSID_PW) 

# Search for up to 10 seconds for network connection
max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    intled.value(1)
    print('waiting for connection...')
    sleep(1)

# Raise an error if Pico is unable to connect
if wlan.status() != 3:
    intled.value(0)
    raise RuntimeError('network connection failed')
else:
    print('WLAN connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )

# Open a socket
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)

# Display your IP address
print('listening on', addr)

# Main loop
while True:

    try:
        # client connects
        cl, addr = s.accept()
        print('client connected from', addr)
        request = cl.recv(1024)
        request = str(request)
        print(request)
        
        # blink the LED
        intled.value(0)
        
        # Read temp from onboard sensor
        picotemp = ReadPicoTemp()
        
        # get pool temp
        pooltemp = ReadDS18b20Temp(poolsensor)
       
        # get pond temp
        pondtemp = ReadDS18b20Temp(pondsensor)

        # get DHT reading
        DHTread = ReadDHTSensor()

        # get WLAN Signal Strength
        wlanrssi = GetWLANStr(variables.SSID)

        # print temp details
        print(f"Pico Temperature: {picotemp}°C")
        print(f"Pool Temperature: {pooltemp}°C")
        print(f"Pond Temperature: {pondtemp}°C")
        print(f"Air Temperature: {DHTread["temp"]}°C")
        print(f"Air Humidity: {DHTread["humidity"]}%")
        print(f"WLAN RSSI: {wlanrssi}db")

        # prep the data to send to Home Assistant as type Json
        data = { "picotemp": picotemp, "pooltemp": pooltemp, "pondtemp": pondtemp, "airtemp": DHTread["temp"], "humidity": DHTread["humidity"], "wlanRSSI": wlanrssi}
        JsonData = json.dumps(data)
        
        # Send headers notifying the receiver that the data is of type Json for application consumption 
        cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
        
        # Send the Json data
        cl.send(JsonData)
        
        # Close the connection
        cl.close()
        
        # blink the LED
        intled.value(1)
        
    except:
        print("code fail (wlan status = " + str(wlan.status()) + ")")
        if wlan.status() <= 0:
            print("trying to reconnect...")
            wlan.disconnect()
            wlan.connect(variables.SSID, variables.SSID_PW)
            if wlan.status() == 3:
                print('connected')

                # Open a socket
                addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

                s = socket.socket()
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(addr)
                s.listen(1)
            else:
                print('connection failed')