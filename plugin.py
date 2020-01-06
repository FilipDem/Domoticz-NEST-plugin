#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Google Nest Python Plugin
#
# Author: Filip Demaertelaere
#
# NEST Plugin that works with the Google Account.
#
# It is based on the PHP code from https://github.com/gboudreau/nest-api. However only the functions required are ported to the plugin.
# A workaround is required to access the Google Account data. The values of issue_token and cookies are specific to your Google Account. 
# To get them, follow these steps (only needs to be done once, as long as you stay logged into your Google Account).
#     Open a Chrome browser tab in Incognito Mode (or clear your cache).
#     Open Developer Tools (View/Developer/Developer Tools).
#     Click on Network tab. Make sure Preserve Log is checked.
#     In the Filter box, enter issueToken
#     Go to https://home.nest.com, and click Sign in with Google. Log into your account.
#     One network call (beginning with iframerpc) will appear in the Dev Tools window. Click on it.
#     In the Headers tab, under General, copy the entire Request URL (beginning with https://accounts.google.com, ending with nest.com). This is your $issue_token.
#     In the Filter box, enter oauth2/iframe
#     Several network calls will appear in the Dev Tools window. Click on the last iframe call.
#     In the Headers tab, under Request Headers, copy the entire cookie value (include the whole string which is several lines long and has many field/value pairs - do not include the Cookie: prefix). This is your $cookies; make sure all of it is on a single line.
#
"""
<plugin key="GoogleNest" name="Nest Thermostat/Protect Google" author="Filip Demaertelaere" version="1.0.0">
    <params>
        <param field="Mode1" label="issue_token" width="600px" required="true"/>
        <param field="Mode2" label="cookie" width="600px" required="true"/>
        <param field="Mode5" label="Minutes between update" width="120px" required="true" default="5"/>
        <param field="Mode6" label="Debug" width="120px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""

#IMPORTS
import Domoticz
import nest
import threading
import time
import json
import fnmatch

#DEVICES TO CREATE
_UNIT_DIMMER = 1

#DEFAULT IMAGE
_NO_IMAGE_UPDATE = -1
_IMAGE_NEST_HEATING = "GoogleNest Nest Heating"
_IMAGE_NEST_AWAY = "GoogleNest Nest Away"
_IMAGE_NEST_PROTECT = "GoogleNest Nest Protect"

#THE HAERTBEAT IS EVERY 10s
_MINUTE = 6

#VALUE TO INDICATE THAT THE DEVICE TIMED-OUT
_TIMEDOUT = 1

#DEBUG
_DEBUG_OFF = 0
_DEBUG_ON = 1

#STATUS
_NEST_UPDATE_STATUS_NONE = 0
_NEST_UPDATE_STATUS_BUSY = 1
_NEST_UPDATE_STATUS_DONE = 2
_NEST_UPDATE_STATUS_UPDATE_SWITCH = 3

#DEVICE NAMES
_NEST_HEATING = 'Heating'
_NEST_ECO_MODE = 'Eco mode'
_NEST_AWAY = 'Away'
_NEST_TEMP_HUM = 'Temp/Hum'
_NEST_HEATING_TEMP = 'Heating Temp'
_NEST_PROTECT = 'Protect'

################################################################################
# Start Plugin
################################################################################

class BasePlugin:

    def __init__(self):
        self.debug = _DEBUG_OFF
        self.nest_update_status = _NEST_UPDATE_STATUS_NONE
        self.NestThread = None
        self.NestPushThread = None
        self.device_to_update = None
        self.device_to_update_level = None
        self.runAgain = 1
        return

    def NestUpdate(self):
        self.nest_update_status = _NEST_UPDATE_STATUS_BUSY
        Domoticz.Debug("Start thread")
        self.myNest.GetNestCredentials()
        Domoticz.Debug("Thread: GetNestCredentials done")
        self.myNest.GetDevicesAndStatus()
        Domoticz.Debug("Thread: GetDevicesAndStatus done")
        Domoticz.Debug("End thread")
        self.nest_update_status = _NEST_UPDATE_STATUS_DONE

    def NestPushUpdate(self, device=None, field=None, value=None):
        self.nest_update_status = _NEST_UPDATE_STATUS_UPDATE_SWITCH
        Domoticz.Debug("Start thread Push")
        if field == 'Target_temperature':
            self.myNest.SetTemperature(device, value)
        elif field == 'Away':
            self.myNest.SetAway(device, value)
        Domoticz.Debug("End thread Push")
        self.nest_update_status = _NEST_UPDATE_STATUS_DONE

    def onStart(self):
        Domoticz.Debug("onStart called")

        # Debugging On/Off
        if Parameters["Mode6"] == "Debug":
            self.debug = _DEBUG_ON
        else:
            self.debug = _DEBUG_OFF
        Domoticz.Debugging(self.debug)

        # Check if images are in database
        if _IMAGE_NEST_AWAY not in Images:
            Domoticz.Image("Nest Away.zip").Create()
        if _IMAGE_NEST_HEATING not in Images:
            Domoticz.Image("Nest Heating.zip").Create()
        if _IMAGE_NEST_PROTECT not in Images:
            Domoticz.Image("Nest Protect.zip").Create()
        Domoticz.Debug("Images created.")

        # Set all devices as timed out
        TimeoutDevice(All=True)

        # Start thread Nest
        self.myNest = nest.Nest(Parameters["Mode1"], Parameters["Mode2"])
        self.NestThread = threading.Thread(name="NestUpdate", target=BasePlugin.NestUpdate, args=(self,)).start()

    def onStop(self):
        Domoticz.Debug("onStop called")

        if (self.NestThread is not None) and self.NestThread.isAlive():
            self.NestThread.join()

        # Wait until queue thread has exited
        Domoticz.Log("Threads still active: " + str(threading.active_count()) + ", should be 1.")
        while (threading.active_count() > 1):
            for thread in threading.enumerate():
                if (thread.name != threading.current_thread().name):
                    Domoticz.Log("'" + thread.name + "' is still running, waiting otherwise Domoticz will abort on plugin exit.")
            time.sleep(1.0)

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        for device in self.myNest.device_list:
            info = self.myNest.GetDeviceInformation(device)
            Domoticz.Debug(info['Where'] + ' - ' + Devices[Unit].Name)
            if info['Where'] in Devices[Unit].Name:
                if _NEST_HEATING_TEMP in Devices[Unit].Name:
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, 'Target_temperature', Level)).start()
                elif _NEST_AWAY in Devices[Unit].Name:
                    if Command == 'On':
                        Level = True
                    else:
                        Level = False
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, 'Away', Level)).start()
                elif _NEST_ECO_MODE in Devices[Unit].Name:
                    if Command == 'On':
                        Level = False
                    else:
                        Level = True
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, 'Away', Level)).start()
                break

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        self.runAgain -= 1
        if self.runAgain <= 0:

            if self.NestThread is None:
                self.NestThread = threading.Thread(name="NestThread", target=BasePlugin.NestUpdate, args=(self,)).start()

            # Run again following the period in the settings
            self.runAgain = _MINUTE*int(Parameters["Mode5"])

        else:
            Domoticz.Debug("onHeartbeat called, run again in "+str(self.runAgain)+" heartbeats.")

            if self.nest_update_status == _NEST_UPDATE_STATUS_DONE:
                Domoticz.Debug("Number of NEST devices: " + str(len(self.myNest.device_list)+len(self.myNest.protect_list)))

                for device in self.myNest.device_list:
                    info = self.myNest.GetDeviceInformation(device)
                    Domoticz.Debug(json.dumps(info))

                    #Update NEST HEATING and create device if required
                    device_name = info['Where'] + ' ' + _NEST_HEATING
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_HEATING].ID, Used=1).Create()
                    if info['Heating']:
                        UpdateDeviceByName(device_name, 1, 1)
                    else:
                        UpdateDeviceByName(device_name, 0, 0)

                    #Update NEST AWAY and create device if required
                    device_name = info['Where'] + ' ' + _NEST_AWAY
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_AWAY].ID, Used=1).Create()
                    if info['Away']:
                        UpdateDeviceByName(device_name, 1, 1)
                    else:
                        UpdateDeviceByName(device_name, 0, 0)

                    #Update NEST ECO MODE and create device if required
                    device_name = info['Where'] + ' ' + _NEST_ECO_MODE
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_AWAY].ID, Used=1).Create()
                    if info['Eco']:
                        UpdateDeviceByName(device_name, 1, 1)
                    else:
                        UpdateDeviceByName(device_name, 0, 0)

                    #Update NEST TEMP/HUMIDITY and create device if required
                    device_name = info['Where'] + ' ' + _NEST_TEMP_HUM
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=82, Subtype=5, Switchtype=0, Used=1).Create()
                    UpdateDeviceByName(device_name, info['Current_temperature'], '%.2f;%.2f;0'%(info['Current_temperature'], info['Humidity']))

                    #Update NEST HEATING TEMPERATUR and create device if required
                    device_name = info['Where'] + ' ' + _NEST_HEATING_TEMP
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=242, Subtype=1, Switchtype=0, TypeName=info['Temperature_scale'], Used=1).Create()
                    UpdateDeviceByName(device_name, info['Target_temperature'], info['Target_temperature'])

                for device in self.myNest.protect_list:
                    info = self.myNest.GetProtectInformation(device)
                    Domoticz.Debug(json.dumps(info))
                    #Create device if required and allowed
                    device_name = info['Where'] + ' ' + _NEST_PROTECT
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=5, Image=Images[_IMAGE_NEST_PROTECT].ID, Used=1).Create()
                    if info['Smoke_status']:
                        UpdateDeviceByName(device_name, 1, 1)
                    else:
                        UpdateDeviceByName(device_name, 0, 0)

                self.nest_update_status = _NEST_UPDATE_STATUS_NONE

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

################################################################################
# Generic helper functions
################################################################################

#DUMP THE PARAMETER
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))

def UpdateDeviceByName(name, nValue, sValue):
    for Unit in Devices:
        if name in Devices[Unit].Name:
            UpdateDevice(Devices[Unit].Unit, nValue, sValue)
            break

def UpdateDevice(Unit, nValue, sValue, Image=_NO_IMAGE_UPDATE, TimedOut=0, AlwaysUpdate=False):
    if Unit in Devices:
        if Devices[Unit].nValue != int(nValue) or Devices[Unit].sValue != str(sValue) or Devices[Unit].TimedOut != TimedOut or AlwaysUpdate:
            if Image != _NO_IMAGE_UPDATE:
                Devices[Unit].Update(nValue=int(nValue), sValue=str(sValue), Image=Image, TimedOut=TimedOut)
            else:
                Devices[Unit].Update(nValue=int(nValue), sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Debug("Update " + Devices[Unit].Name + ": " + str(nValue) + " - '" + str(sValue) + "'")

#SET DEVICE ON TIMED-OUT (OR ALL DEVICES)
def TimeoutDevice(All, Unit=0):
    if All:
        for x in Devices:
            UpdateDevice(x, Devices[x].nValue, Devices[x].sValue, TimedOut=_TIMEDOUT)
    else:
        UpdateDevice(Unit, Devices[Unit].nValue, Devices[Unit].sValue, TimedOut=_TIMEDOUT)

#CREATE ALL THE DEVICES (USED)
def CreateDevicesUsed():
    if (_UNIT_DIMMER not in Devices):
        Domoticz.Device(Name="Cooling Fan", Unit=_UNIT_DIMMER, TypeName="Dimmer", Image=Images[_IMAGE].ID, Used=1).Create()

#CREATE ALL THE DEVICES (NOT USED)
def CreateDevicesNotUsed():
    pass

#GET CPU TEMPERATURE
def getCPUtemperature():
    try:
        res = os.popen("cat /sys/class/thermal/thermal_zone0/temp").readline()
    except:
        res = "0"
    return round(float(res)/1000,1)
