import asyncio
import os
from pybms import jbd, tools
mac = "70:3E:97:EB:37:16"
battery = jbd.JBDBattery(mac)
asyncio.run(battery.read_once())


path = "/home/pi/Documents/" + mac.replace(":", "") + '.pkl'
tools.pickle_append(path, battery)