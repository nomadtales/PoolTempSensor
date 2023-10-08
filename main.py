# Import required libraries
import network
import socket
import time
from time import sleep
import onewire
import ds18x20
import machine
import json
import variables # custom variables file

# sensors
poolsensor = variables.poolsensor
airsensor = variables.airsensor

# setup internal temp and LED
adcpin = 4
inttemp = machine.ADC(adcpin)
intled = machine.Pin("LED", machine.Pin.OUT)

# setup ds18b20 sensor(s)
ds_pin = machine.Pin(22)
sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = sensor.scan()

# check sensor exists
print('Found DS devices: ', roms)

# function for internal temp
def ReadPicoTemp():
    adc_value = inttemp.read_u16()
    volt = (3.3/65535) * adc_value
    temperature = 27 - (volt - 0.706)/0.001721
    return round(temperature, 1)

# function for ds18b20 sensor(s) temps
def ReadDS18b20Temp(ds_sensor):
    err = None
    temp = None
    try:
        # convert temp
        sensor.convert_temp()
        # pause
        time.sleep_ms(750)
        # get temp
        temp = sensor.read_temp(ds_sensor)
        # pause
        time.sleep_ms(750)
    except Exception as err:
        print('Error: ', err)
    return temp

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

while True:
    # If pico is connected to wifi put the onboard LED on else off
    if wlan.status() == 3: 
        intled.value(1)
    else:
        intled.value(0)
         
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
        
        # get air temp
        airtemp = ReadDS18b20Temp(airsensor)

        # print temp details
        print(f"Pico Temperature: {picotemp}°C")
        print(f"Pool Temperature: {pooltemp}°C")
        print(f"Air Temperature: {airtemp}°C")

        # prep the data to send to Home Assistant as type Json
        data = { "picotemp": picotemp, "pooltemp": pooltemp, "airtemp": airtemp }
        JsonData = json.dumps(data)
        
        # Send headers notifying the receiver that the data is of type Json for application consumption 
        cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
        
        # Send the Json data
        cl.send(JsonData)
        
        # Close the connection
        cl.close()
        
        # blink the LED
        intled.value(1)
        
    except OSError as e:
        cl.close()
        print('connection closed')