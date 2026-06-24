#!/usr/bin/env python
# coding: utf-8

# In[2]:

# Imports ##############################################################################

import requests
import json
import time
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import paho.mqtt.client as mqtt
import pygame
import random
import threading
from datetime import datetime
import math
from aiocoap import *
import json
import asyncio

############## Data Proxy initializers #################################################

url = "http://192.168.13.126:5000/data"
bucket = "Art_AVZ"
org = "ca01f5f07193702e"
token = "cMkFiUm1d_UPI7AYdkQJEjV8wO1pkN4eCTZk-7baPtlRFTKU6KpbkzAu6cn6oD3EpfnhoV1zdaswY9OjBibi5g=="

http = True
coap = False

tempValue = 0
humValue = 0
lightValue = 0
moveValue = 0
movement = 0

url_flux="https://eu-central-1-1.aws.cloud2.influxdata.com"

client = influxdb_client.InfluxDBClient(
   url=url_flux,
   token=token,
   org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)

#### Sensor Read ###########################################################

# HTTP
def readSensorHTTP(sensorType):
    if (sensorType == "temp"):
        label = "temp"
    elif (sensorType == "hum"):
        label = "hum"
    elif (sensorType == "light"):
        label = "light"
    elif (sensorType == "move"):
        label = "move"
    jsonDocument = requests.get(url).content
    jsonDocument = jsonDocument.decode("utf-8")
    value = json.loads(jsonDocument)[label]
    return value

# COAP
async def readSensorCOAP():
    global tempValue, lightValue, humValue, moveValue
    protocol = await Context.create_client_context()
    request = Message(code=GET, uri="coap://192.168.13.3/Espressif")  # Root path

    try:
        response = await protocol.request(request).response
    except Exception as e:
        print(f"Failed to contact server: {e}")
    else:
        print(f"Server responded: {response.code}")
        print(f"Payload: {response.payload.decode('utf-8') if response.payload else 'No payload'}")

    data = json.loads(response.payload.decode('utf-8') )  # Converts to a Python dict

    tempValue = data["temp"]
    humValue = data["hum"]
    moveValue = data["move"]
    lightValue = data["light"]

####################### MQTT ###############################################

def sample(input):
    publish.single("esp32/sampling_rate", input, hostname="192.168.13.126")

def motion(input):
    publish.single("esp32/motion_alert", input, hostname="192.168.13.126")

def protocol(input):
    global http, coap
    publish.single("esp32/protocol", input, hostname="192.168.13.126")
    if(input == "http"):
        http = True
        coap = False
    elif(input == "coap"):
        http = False
        coap = True


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("esp32/movement")

def on_message(client, userdata, msg):
    global movement
    movement = float(msg.payload)
    print(f"movement detected : {movement}")

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect("192.168.13.126", 1883, 60)

#mqttc.loop_forever()

#mosquitto_sub -t esp32/motion_alert -h localhost
#mosquitto_pub -t esp32/sampling_rate -h 192.168.171.126 -m “temp:100”
###################################################################        

# Data Proxy Thread ###############################################

def data_proxy():
    global tempValue, lightValue, humValue, moveValue, http, coap
    mqttc.loop_start() 

    while True:

        if(http):
            #receiving data using http
            tempValue = readSensorHTTP("temp")
            humValue =  readSensorHTTP("hum")
            lightValue =  readSensorHTTP("light")
            moveValue =  readSensorHTTP("move")


        elif (coap):
            #receiving data using coap
            asyncio.run(readSensorCOAP())

        p = influxdb_client.Point("Sensors")\
            .tag("location", "Bologna")\
            .field("Temperature", tempValue)\
            .field("Humidity", humValue)\
            .field("Light", lightValue)
        
        write_api.write(bucket=bucket, org=org, record=p)

        print(f"Temperature is {tempValue}°C")
        print(f"Humidity is {humValue}%")
        print(f"Light level is {lightValue} lux")
        
        time.sleep(1)

#################################################################

# visualizer initializers #######################################

width = 1280
height = 720

rain_img = pygame.image.load(r"C:\Users\Alireza\Desktop\University Stuff\Unibo\Iot\rain.png")
sun_img = pygame.image.load(r"C:\Users\Alireza\Desktop\University Stuff\Unibo\Iot\sun.png")
moon_img = pygame.image.load(r"C:\Users\Alireza\Desktop\University Stuff\Unibo\Iot\moon.png")

sun_rect = sun_img.get_rect(center=(width/2, height/2))
moon_rect = moon_img.get_rect(center=(width/2, height/2))



class Rain(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image= rain_img
        self.rect=self.image.get_rect()
        self.speedx=3
        self.speedy=random.randint(5,25)
        self.rect.x=random.randint(-100,width)
        self.rect.y=random.randint(-height, -5)

    def update(self):

        if self.rect.bottom>height:
            self.speedx=3
            self.speedy=random.randint(5,25)
            self.rect.x=random.randint(-100,width)
            self.rect.y=random.randint(-height, -5)

        self.rect.x=self.rect.x+self.speedx
        self.rect.y=self.rect.y+self.speedy

rain_group = pygame.sprite.Group()

class Heatwave:

    def __init__(self):
        self.center = (width/2 , height/2)
        self.radius = 512/2
        
    def draw(self, surface,temp, phase, move):
        wave_length = 40 + temp * 2    # length of wave lines depends on temp
        amplitude = 10 + temp          # wave height depends on temp
        num_waves = 30 

        for i in range(num_waves):
            angle = (360 / num_waves) * i
            angle_rad = math.radians(angle)
            start_x = (self.center[0]+move) + math.cos(angle_rad) * (self.radius + 10)
            start_y = self.center[1] + math.sin(angle_rad) * (self.radius + 10)
            points = []

            for t in range(30):
                # Linear distance along the wave
                pos = t / 30 * wave_length

                # Base point along the main direction
                base_x = start_x + math.cos(angle_rad) * pos
                base_y = start_y + math.sin(angle_rad) * pos

                # Calculate perpendicular offset using sine wave for heatwave effect
                perp_angle = angle_rad + math.pi / 2
                offset = math.sin(t * 0.3 + phase) * amplitude

                x = base_x + math.cos(perp_angle) * offset
                y = base_y + math.sin(perp_angle) * offset

                points.append((x, y))

            pygame.draw.lines(surface, (255, 150, 0), False, points, 2)




light_list = [10]

def update_brightness(new_light_value, max_samples=10):
    light_list.append(new_light_value)
    if len(light_list) > max_samples:
        del light_list[0]
    avg_light = sum(light_list) / len(light_list)
    brightness = max(0, min(int(avg_light)*1.5, 255))
    return brightness

def update_movement(movement):
    direction = random.choice(["left", "right"])
    movement = movement/20
    movement = max(0, min(movement, 100))
    if (direction=="left"):
        movement = (-movement)
    elif (direction=="right"):
        movement = (movement)
    return movement

        

###########################################################


# visualizer Thread #######################################

def visualizer():

    global tempValue, lightValue, humValue, moveValue, movement
    current_rain_drops = 0
    phase = 0
    pygame.init()
    screen = pygame.display.set_mode((width,height))
    clock = pygame.time.Clock()

    while True:

        if(current_rain_drops < humValue):
            rain=Rain()
            rain_group.add(rain)
            current_rain_drops+=1

        elif(current_rain_drops > humValue):
            rain = random.choice(rain_group.sprites())
            rain_group.remove(rain)
            current_rain_drops-=1

        current_time = datetime.now()
        hour = current_time.hour

        if(6<hour<21):
            day = True
            night = False
        else:
            day = False
            night = True
   
        brightness = update_brightness(lightValue)

        # Process player inputs.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:

                pygame.quit()
                raise SystemExit

        # Do logical updates here.
        # ...
        x_movement = update_movement(movement)
        screen.fill((0, brightness, brightness))  # Fill the display with a solid color
        phase +=0.1
        hw = Heatwave()
        hw.draw(screen, tempValue, phase, x_movement)
        
        if(day):

            screen.blit(sun_img, sun_rect)

        if(night):
            screen.blit(moon_img, moon_rect)

        sun_rect.x += x_movement
        movement = 0
        rain_group.update()
        rain_group.draw(screen)
        pygame.display.flip()  # Refresh on-screen display
        clock.tick(30)         # wait until next frame (at 60 FPS)

#####################################################

#### Threads ########################################

visualizer_thread = threading.Thread(target=visualizer)
data_proxy_thread = threading.Thread(target=data_proxy)
data_proxy_thread.start()
visualizer_thread.start()



# In[ ]: