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
    <description>
        <h2>Instructions</h2>
        The values of <b>issue_token</b> and <b>cookies</b> are specific to your Google Account.<br/>
        To get them, follow these steps (only needs to be done once, as long as you stay logged into your Google Account).<br/>
        <ol>
          <li>Open a Chrome browser tab in <b>Incognito Mode</b> (or clear your cache).</li>
          <li>Open '<b>Developer Tools</b>' (View/Developer/Developer Tools).</li>
          <li>Click on 'Network' tab. Make sure '<b>Preserve Log</b>' is checked.</li>
          <li>In the 'Filter' box, enter '<b>issueToken</b>'</li>
          <li>Go to '<b>https://home.nest.com</b>', and click 'Sign in with Google'. Log into your account.</li>
          <li>One network call (beginning with '<b>iframerpc</b>') will appear in the 'Dev Tools' window. Click on it.</li>
          <li>In the '<b>Headers</b>' tab, under '<b>General</b>', copy the entire '<b>Request URL</b>' (beginning with https://accounts.google.com, ending with nest.com). This is your <b>$issue_token</b>.</li>
          <li>In the 'Filter' box, enter '<b>oauth2/iframe</b>'.</li>
          <li>Several network calls will appear in the 'Dev Tools' window. Click on the <b>last 'iframe'</b> call.</li>
          <li>In the '<b>Headers</b>' tab, under '<b>Request Headers</b>', copy the entire '<b>cookie value</b>' (include the whole string which is several lines long and has many field/value pairs - do not include the Cookie: prefix). This is your <b>$cookies</b>; make sure all of it is on a single line.</li>
        </ol>
    </description>
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
_IMAGE_NEST_HEATING = "GoogleNest Nest Heating"
_IMAGE_NEST_HEATING_OFF = "GoogleNest Nest Heating Off"
_IMAGE_NEST_AWAY = "GoogleNest Nest Away"
_IMAGE_NEST_ECO = "GoogleNest Nest Eco"
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
        self.access_error_generated = 0
        self.runAgain = 1
        return

    def NestUpdate(self):
        self.nest_update_status = _NEST_UPDATE_STATUS_BUSY
        Domoticz.Debug("Start thread")
        if self.myNest.UpdateDevices():
            self.access_error_generated = 0
            Domoticz.Debug("End thread (OK)")
        else:
            Domoticz.Debug("End thread (ERROR)")
            TimeoutDevice(All=True)
            if self.access_error_generated <= 0:
                Domoticz.Error(self.myNest.GetAccessError())
                self.access_error_generated = 43201 #12h*60min*60s
        self.nest_update_status = _NEST_UPDATE_STATUS_DONE

    def NestPushUpdate(self, device=None, field=None, value=None, device_name=None):
        self.nest_update_status = _NEST_UPDATE_STATUS_UPDATE_SWITCH
        Domoticz.Debug("Start thread Push")
        if field == _NEST_HEATING_TEMP:
            if self.myNest.SetTemperature(device, value):
                UpdateDeviceByName(device_name, value, value, Images[_IMAGE_NEST_HEATING].ID)
        elif field == _NEST_AWAY:
            if self.myNest.SetAway(device, value):
                if value == True:
                    UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_AWAY].ID)
                else:
                    UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_AWAY].ID)
        elif field == _NEST_ECO_MODE:
            if self.myNest.SetEco(device, value):
                if value == 'manual-eco':
                    UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_ECO].ID)
                else:
                    UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_ECO].ID)
        elif field == _NEST_HEATING:
            if self.myNest.SetThermostat(device, value):
                if value == 'heat':
                    UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_HEATING_OFF].ID)
                else:
                    UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
        Domoticz.Debug("End thread Push")
        self.nest_update_status = _NEST_UPDATE_STATUS_NONE

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
        if _IMAGE_NEST_ECO not in Images:
            Domoticz.Image("Nest Eco.zip").Create()
        if _IMAGE_NEST_HEATING not in Images:
            Domoticz.Image("Nest Heating.zip").Create()
        if _IMAGE_NEST_HEATING_OFF not in Images:
            Domoticz.Image("Nest Heating Off.zip").Create()
        if _IMAGE_NEST_PROTECT not in Images:
            Domoticz.Image("Nest Protect.zip").Create()
        Domoticz.Debug("Images created.")

        # Set all devices as timed out
        TimeoutDevice(All=True)

        # Start thread Nest
        self.myNest = nest.Nest(Parameters["Mode1"], Parameters["Mode2"])
        #self.NestThread = threading.Thread(name="NestUpdate", target=BasePlugin.NestUpdate, args=(self,)).start()

    def onStop(self):
        Domoticz.Debug("onStop called")

        self.myNest.terminate()
        if (self.NestThread is not None) and self.NestThread.isAlive():
            self.NestThread.join(1)

        # Wait until queue thread has exited
        Domoticz.Debug("Threads still active: " + str(threading.active_count()) + ", should be 1.")
        Domoticz.Debug("Current thread (plugin): "+threading.current_thread().name) 
        while (threading.active_count() > 1):
            for thread in threading.enumerate():
                if (thread.name != threading.current_thread().name):
                    Domoticz.Log("'" + thread.name + "' is still running, waiting otherwise Domoticz will abort on plugin exit.")
            time.sleep(0.5)

        time.sleep(1)

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
                    device_name = info['Where'] + ' ' + _NEST_HEATING_TEMP
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, _NEST_HEATING_TEMP, Level, device_name)).start()
                elif _NEST_AWAY in Devices[Unit].Name:
                    device_name = info['Where'] + ' ' + _NEST_AWAY
                    if Command == 'On':
                        Level = True
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_AWAY].ID)
                    else:
                        Level = False
                        UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_AWAY].ID)
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, _NEST_AWAY, Level, device_name)).start()
                elif _NEST_ECO_MODE in Devices[Unit].Name:
                    device_name = info['Where'] + ' ' + _NEST_ECO_MODE
                    if Command == 'On':
                        Level = 'manual-eco'
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_ECO].ID)
                    else:
                        Level = 'schedule'
                        UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_ECO].ID)
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, _NEST_ECO_MODE, Level, device_name)).start()
                elif _NEST_HEATING in Devices[Unit].Name:
                    device_name = info['Where'] + ' ' + _NEST_HEATING
                    if Command == 'On':
                        Level = 'heat'
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_HEATING].ID)
                    else:
                        Level = 'off'
                        UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
                    if self.NestPushThread is None:
                        self.NestPushThread = threading.Thread(name="NestPushThread", target=BasePlugin.NestPushUpdate, args=(self, device, _NEST_HEATING, Level, device_name)).start()
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

            # Generate en error every x time
            if self.access_error_generated > 0:
                self.access_error_generated -= _MINUTE*int(Parameters["Mode5"])

        else:
            Domoticz.Debug("onHeartbeat called, run again in "+str(self.runAgain)+" heartbeats.")

            if self.nest_update_status == _NEST_UPDATE_STATUS_DONE and self.access_error_generated == 0:
                Domoticz.Debug("Number of NEST devices: " + str(len(self.myNest.device_list)+len(self.myNest.protect_list)))

                for device in self.myNest.device_list:
                    info = self.myNest.GetDeviceInformation(device)
                    Domoticz.Debug(json.dumps(info))

                    #Update NEST HEATING and create device if required
                    device_name = info['Where'] + ' ' + _NEST_HEATING
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_HEATING].ID, Used=1).Create()
                    if info['Heating']:
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_HEATING].ID)
                    else:
                        #Update NEST HEATING icon off or on
                        if info['Target_mode'] == 'off':
                            UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
                        else:
                            UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_HEATING].ID)

                    #Update NEST AWAY and create device if required
                    device_name = info['Where'] + ' ' + _NEST_AWAY
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_AWAY].ID, Used=1).Create()
                    if info['Away']:
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_AWAY].ID)
                    else:
                        UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_AWAY].ID)

                    #Update NEST ECO MODE and create device if required
                    device_name = info['Where'] + ' ' + _NEST_ECO_MODE
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_ECO].ID, Used=1).Create()
                    if info['Eco']:
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_ECO].ID)
                    else:
                        UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_ECO].ID)

                    #Update NEST TEMP/HUMIDITY and create device if required
                    device_name = info['Where'] + ' ' + _NEST_TEMP_HUM
                    if not fnmatch.filter([Devices[x].Name for x in Devices], '*'+device_name):
                        Domoticz.Device(Unit=len(Devices)+1, Name=device_name, Type=82, Subtype=5, Switchtype=0, Used=1).Create()
                    UpdateDeviceByName(device_name, info['Current_temperature'], '%.2f;%.2f;0'%(info['Current_temperature'], info['Humidity']))

                    #Update NEST HEATING TEMPERATURE and create device if required
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
                        UpdateDeviceByName(device_name, 1, 1, Images[_IMAGE_NEST_PROTECT].ID, BatteryLevel=int(int(info['Battery_level'])/100))
                    else:
                        UpdateDeviceByName(device_name, 0, 0, Images[_IMAGE_NEST_PROTECT].ID, BatteryLevel=int(int(info['Battery_level'])/100))

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

#UPDATE THE DEVICE BY USING THE NAME OF THE DEVICE
def UpdateDeviceByName(name, nValue, sValue, Image=-1, BatteryLevel=255):
    for Unit in Devices:
        if name in Devices[Unit].Name:
            if Image == -1:
                Image = Devices[Devices[Unit].Unit].Image
            UpdateDevice(Devices[Unit].Unit, nValue, sValue, Image)
            if BatteryLevel != 255:
                UpdateDeviceBatSig(Devices[Unit].Unit, BatteryLevel)
            break

#UPDATE THE DEVICE
def UpdateDevice(Unit, nValue, sValue, Image, TimedOut=0, AlwaysUpdate=False):
    if Unit in Devices:
        if Devices[Unit].nValue != int(nValue) or Devices[Unit].sValue != str(sValue) or Devices[Unit].TimedOut != TimedOut or Devices[Unit].Image != Image or AlwaysUpdate:
            Domoticz.Debug("Going to Update " + Devices[Unit].Name + ": " + str(nValue) + " - '" + str(sValue) + "'")
            Devices[Unit].Update(nValue=int(nValue), sValue=str(sValue), Image=Image, TimedOut=TimedOut)
            Domoticz.Debug("Updated " + Devices[Unit].Name + ": " + str(nValue) + " - '" + str(sValue) + "'")
        else:
            Devices[Unit].Touch()

#UPDATE THE BATTERY LEVEL AND SIGNAL STRENGTH OF A DEVICE
def UpdateDeviceBatSig(Unit, BatteryLevel=255, SignalLevel=12):
    if Unit in Devices:
        if Devices[Unit].BatteryLevel != int(BatteryLevel) or Devices[Unit].SignalLevel != int(SignalLevel):
            Domoticz.Debug("Going to Update " + Devices[Unit].Name + ": " + str(Devices[Unit].nValue) + " - '" + str(Devices[Unit].sValue) + "' - " + str(BatteryLevel) + " - " + str(SignalLevel))
            Devices[Unit].Update(nValue=Devices[Unit].nValue, sValue=Devices[Unit].sValue, BatteryLevel=int(BatteryLevel), SignalLevel=int(SignalLevel))
            Domoticz.Debug("Updated " + Devices[Unit].Name + ": " + str(Devices[Unit].nValue) + " - '" + str(Devices[Unit].sValue) + "' - " + str(BatteryLevel) + " - " + str(SignalLevel))

#SET DEVICE ON TIMED-OUT (OR ALL DEVICES)
def TimeoutDevice(All, Unit=0):
    if All:
        for x in Devices:
            UpdateDevice(x, Devices[x].nValue, Devices[x].sValue, Devices[x].Image, TimedOut=_TIMEDOUT)
    else:
        UpdateDevice(Unit, Devices[Unit].nValue, Devices[Unit].sValue, Devices[Unit].Image, TimedOut=_TIMEDOUT)

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
