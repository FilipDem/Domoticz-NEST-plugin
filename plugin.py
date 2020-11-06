#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Google Nest Python Plugin
#
# Author: Filip Demaertelaere
# Extended by Mark Ruys
#
# Nest Plugin that works with the Google Account.
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
<plugin key="GoogleNest" name="Nest Thermostat/Protect Google" author="Filip Demaertelaere" version="1.1.0">
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

#DEVICES TO CREATE
_UNIT_DIMMER = 1

#DEFAULT IMAGE
_IMAGE_NEST_HEATING = "GoogleNest Nest Heating"
_IMAGE_NEST_HEATING_OFF = "GoogleNest Nest Heating Off"
_IMAGE_NEST_AWAY = "GoogleNest Nest Away"
_IMAGE_NEST_ECO = "GoogleNest Nest Eco"
_IMAGE_NEST_PROTECT = "GoogleNest Nest Protect"

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
_NEST_ECO_MODE = 'Eco Mode'
_NEST_AWAY = 'Away'
_NEST_TEMP_HUM = 'Temp/Hum'
_NEST_HEATING_TEMP = 'Heating Temp'
_NEST_PROTECT = 'Protect'

################################################################################
# Start Plugin
################################################################################

class BasePlugin:

    HEARTBEAT_SEC = 10

    def __init__(self):
        self.debug = _DEBUG_OFF
        self.nest_update_status = _NEST_UPDATE_STATUS_NONE
        self.NestThread = None
        self.NestPushThread = None
        self.access_error_generated = 0
        self.runAgain = 0
        return

    def NestUpdate(self):
        self.nest_update_status = _NEST_UPDATE_STATUS_BUSY
        Domoticz.Debug("> Entering update thread")
        if self.myNest.UpdateDevices():
            self.access_error_generated = 0
        else:
            Domoticz.Error(self.myNest.GetAccessError())
            TimeoutDevice(All=True)
            if self.access_error_generated <= 0:
                self.access_error_generated = 12 * 60 * 60 # 12 hours
        Domoticz.Debug("> Exit update thread")
        self.nest_update_status = _NEST_UPDATE_STATUS_DONE

    def NestPushUpdate(self, device, field, value, Unit):
        self.nest_update_status = _NEST_UPDATE_STATUS_UPDATE_SWITCH
        Domoticz.Debug("> Entering push thread")
        if field == _NEST_HEATING_TEMP:
            if self.myNest.SetTemperature(device, value):
                UpdateDeviceByUnit(Unit, value, value, Images[_IMAGE_NEST_HEATING].ID)
        elif field == _NEST_AWAY:
            if self.myNest.SetAway(device, value):
                if value == True:
                    UpdateDeviceByUnit(Unit, 1, 1, Images[_IMAGE_NEST_AWAY].ID)
                else:
                    UpdateDeviceByUnit(Unit, 0, 0, Images[_IMAGE_NEST_AWAY].ID)
        elif field == _NEST_ECO_MODE:
            if self.myNest.SetEco(device, value):
                if value == 'manual-eco':
                    UpdateDeviceByUnit(Unit, 1, 1, Images[_IMAGE_NEST_ECO].ID)
                else:
                    UpdateDeviceByUnit(Unit, 0, 0, Images[_IMAGE_NEST_ECO].ID)
        elif field == _NEST_HEATING:
            if self.myNest.SetThermostat(device, value):
                if value == 'heat':
                    UpdateDeviceByUnit(Unit, 1, 1, Images[_IMAGE_NEST_HEATING_OFF].ID)
                else:
                    UpdateDeviceByUnit(Unit, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
        Domoticz.Debug("> Exit push thread")
        self.nest_update_status = _NEST_UPDATE_STATUS_NONE

    def onStart(self):
        # Set debug level according to user setting
        self.debug = _DEBUG_ON if Parameters["Mode6"] == "Debug" else _DEBUG_OFF
        Domoticz.Debugging(self.debug)

        # Show plugin configuration in log
        if self.debug == _DEBUG_ON:
            DumpConfigToLog()

        # Create images if necessary
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
        Domoticz.Debug("> Images created")

        # Set all devices as timed out
        TimeoutDevice(All=True)

        # Create Nest instance
        self.myNest = nest.Nest(Parameters["Mode1"], Parameters["Mode2"])

        Domoticz.Debug("> Plugin started")

    def onStop(self):
        self.myNest.terminate()

        # Wait until all queued threads have exited
        while threading.active_count() > 1:
            for thread in threading.enumerate():
                if thread.name != threading.current_thread().name:
                    Domoticz.Log("Thread {} is still running, wait some more".format(thread.name))
            time.sleep(0.5)

        Domoticz.Debug("> Plugin stopped")
        time.sleep(1)

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("> onConnect called, ignored")

    def onMessage(self, Connection, Data):
        Domoticz.Debug("> onMessage called, ignored")

    def startNestPushThread(self, device, field, Level, Unit):
        if self.NestPushThread is not None and self.NestPushThread.isAlive():
            Domoticz.Error("NestPushThread still running, command ignored")
        else:
            self.NestPushThread = threading.Thread(
                name="NestPushThread",
                target=BasePlugin.NestPushUpdate,
                args=(self, device, field, Level, Unit)
            )
            self.NestPushThread.start()

    def onCommand(self, Unit, Command, Level, Hue):
        for device in self.myNest.device_list:
            info = self.myNest.GetDeviceInformation(device)
            Domoticz.Debug("> {} - {}".format(info['Where'], Devices[Unit].Name))

            if DeviceNameIsUnit(info['Where'] + ' ' + _NEST_HEATING_TEMP, Unit):
                self.startNestPushThread(device, _NEST_HEATING_TEMP, Level, Unit)
            elif DeviceNameIsUnit(info['Where'] + ' ' + _NEST_AWAY, Unit):
                if Command == 'On':
                    Level = True
                    UpdateDeviceByUnit(Unit, 1, 1, Images[_IMAGE_NEST_AWAY].ID)
                else:
                    Level = False
                    UpdateDeviceByUnit(Unit, 0, 0, Images[_IMAGE_NEST_AWAY].ID)
                self.startNestPushThread(device, _NEST_AWAY, Level, Unit)
            elif DeviceNameIsUnit(info['Where'] + ' ' + _NEST_ECO_MODE, Unit):
                if Command == 'On':
                    Level = 'manual-eco'
                    UpdateDeviceByUnit(Unit, 1, 1, Images[_IMAGE_NEST_ECO].ID)
                else:
                    Level = 'schedule'
                    UpdateDeviceByUnit(Unit, 0, 0, Images[_IMAGE_NEST_ECO].ID)
                self.startNestPushThread(device, _NEST_ECO_MODE, Level, Unit)
            elif DeviceNameIsUnit(info['Where'] + ' ' + _NEST_HEATING, Unit):
                if Command == 'On':
                    Level = 'heat'
                    UpdateDeviceByUnit(Unit, 1, 1, Images[_IMAGE_NEST_HEATING].ID)
                else:
                    Level = 'off'
                    UpdateDeviceByUnit(Unit, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
                self.startNestPushThread(device, _NEST_HEATING, Level, Unit)

        Domoticz.Status("Processed {} to {} for unit {}".format(Command, Level, Unit))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("> Notification: {}, {}, {}, {}, {}, {}, {}".format(
            Name, Subject, Text, Status, Priority, Sound, ImageFile
        ))

    def onDisconnect(self, Connection):
        Domoticz.Debug("> onDisconnect called, ignored")

    def onHeartbeat(self):
        self.runAgain -= self.HEARTBEAT_SEC

        # In case the API fails, generate en error every 12 hours
        if self.access_error_generated > 0:
            self.access_error_generated -= self.HEARTBEAT_SEC

        if self.runAgain <= 0:
            if self.NestThread is not None and self.NestThread.isAlive():
                Domoticz.Error("NestThread still running")
            else:
                self.NestThread = threading.Thread(name="NestThread", target=BasePlugin.NestUpdate, args=(self,))
                self.NestThread.start()

            # Run again following the period in the settings
            self.runAgain = int(Parameters["Mode5"]) * 60

        elif self.nest_update_status == _NEST_UPDATE_STATUS_DONE and self.access_error_generated <= 0:
            updated_units = 0
            for nest_device in self.myNest.device_list:
                info = self.myNest.GetDeviceInformation(nest_device)
                Domoticz.Debug("> {}".format(json.dumps(info)))

                #Update NEST HEATING and create device if required
                device_name = info['Where'] + ' ' + _NEST_HEATING
                unit = FindUnitByNestName(device_name)
                if not unit:
                    unit = CreateNewUnit()
                    description = CreateDescription(device_name)
                    Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_HEATING].ID, Used=1).Create()
                if info['Heating']:
                    UpdateDeviceByUnit(unit, 1, 1, Images[_IMAGE_NEST_HEATING].ID)
                else:
                    #Update NEST HEATING icon off or on
                    if info['Target_mode'] == 'off':
                        UpdateDeviceByUnit(unit, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
                    else:
                        UpdateDeviceByUnit(unit, 0, 0, Images[_IMAGE_NEST_HEATING].ID)
                updated_units += 1

                #Update NEST AWAY and create device if required
                device_name = info['Where'] + ' ' + _NEST_AWAY
                unit = FindUnitByNestName(device_name)
                if not unit:
                    unit = CreateNewUnit()
                    description = CreateDescription(device_name)
                    Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_AWAY].ID, Used=1).Create()
                if info['Away']:
                    UpdateDeviceByUnit(unit, 1, 1, Images[_IMAGE_NEST_AWAY].ID)
                else:
                    UpdateDeviceByUnit(unit, 0, 0, Images[_IMAGE_NEST_AWAY].ID)
                updated_units += 1

                #Update NEST ECO MODE and create device if required
                device_name = info['Where'] + ' ' + _NEST_ECO_MODE
                unit = FindUnitByNestName(device_name)
                if not unit:
                    unit = CreateNewUnit()
                    description = CreateDescription(device_name)
                    Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_ECO].ID, Used=1).Create()
                if info['Eco']:
                    UpdateDeviceByUnit(unit, 1, 1, Images[_IMAGE_NEST_ECO].ID)
                else:
                    UpdateDeviceByUnit(unit, 0, 0, Images[_IMAGE_NEST_ECO].ID)
                updated_units += 1

                #Update NEST TEMP/HUMIDITY and create device if required
                device_name = info['Where'] + ' ' + _NEST_TEMP_HUM
                unit = FindUnitByNestName(device_name)
                if not unit:
                    unit = CreateNewUnit()
                    description = CreateDescription(device_name)
                    Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=82, Subtype=5, Switchtype=0, Used=1).Create()
                UpdateDeviceByUnit(unit, info['Current_temperature'], '%.1f;%.0f;0'%(info['Current_temperature'], info['Humidity']))
                updated_units += 1

                #Update NEST HEATING TEMPERATURE and create device if required
                device_name = info['Where'] + ' ' + _NEST_HEATING_TEMP
                unit = FindUnitByNestName(device_name)
                if not unit:
                    unit = CreateNewUnit()
                    description = CreateDescription(device_name)
                    Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=242, Subtype=1, Switchtype=0, TypeName=info['Temperature_scale'], Used=1).Create()
                UpdateDeviceByUnit(unit, info['Target_temperature'], info['Target_temperature'])
                updated_units += 1

            for nest_device in self.myNest.protect_list:
                info = self.myNest.GetProtectInformation(nest_device)
                Domoticz.Debug("> {}".format(json.dumps(info)))
                #Create device if required and allowed
                device_name = info['Where'] + ' ' + _NEST_PROTECT
                unit = FindUnitByNestName(device_name)
                if not unit:
                    unit = CreateNewUnit()
                    description = CreateDescription(device_name)
                    Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=5, Image=Images[_IMAGE_NEST_PROTECT].ID, Used=1).Create()
                if info['Smoke_status']:
                    UpdateDeviceByUnit(unit, 1, 1, Images[_IMAGE_NEST_PROTECT].ID, BatteryLevel=int(int(info['Battery_level'])/100))
                else:
                    UpdateDeviceByUnit(unit, 0, 0, Images[_IMAGE_NEST_PROTECT].ID, BatteryLevel=int(int(info['Battery_level'])/100))
                updated_units += 1

            Domoticz.Status("Updated {} units for {} device(s)".format(
                updated_units,
                len(self.myNest.device_list) + len(self.myNest.protect_list)
            ))
            self.nest_update_status = _NEST_UPDATE_STATUS_NONE

        Domoticz.Debug("Wait {} seconds to update devices".format(self.runAgain))

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
            Domoticz.Debug("> Parameter {}: {}".format(x, Parameters[x]))
    Domoticz.Debug("> Got {} devices:".format(len(Devices)))
    for x in Devices:
        Domoticz.Debug("> Device {}              {}".format(x, Devices[x]))
        Domoticz.Debug("> Device {} ID:          {}".format(x, Devices[x].ID))
        Domoticz.Debug("> Device {} Name:        {}".format(x, Devices[x].Name))
        Domoticz.Debug("> Device {} DeviceID:    {}".format(x, Devices[x].DeviceID))
        Domoticz.Debug("> Device {} Description: {}".format(x, Devices[x].Description))
        Domoticz.Debug("> Device {} nValue:      {}".format(x, Devices[x].nValue))
        Domoticz.Debug("> Device {} sValue:      {}".format(x, Devices[x].sValue))
        Domoticz.Debug("> Device {} LastLevel:   {}".format(x, Devices[x].LastLevel))

def CreateNewUnit():
    # Find the next available unit, starting from 1
    unit = 1
    while unit in Devices:
        unit += 1
    Domoticz.Debug("> Created unit {}".format(unit))
    return unit

def DeviceNameIsUnit(device_name, Unit):
    needle = "[{}]".format(device_name)
    return needle in Devices[Unit].Description

def CreateDescription(tag):
    return "Do not remove: [{}]".format(tag)

def FindUnitByNestName(device_name):
    for Unit in Devices:
        if DeviceNameIsUnit(device_name, Unit):
            return Unit
    return None

#UPDATE THE DEVICE BY USING THE UNIT
def UpdateDeviceByUnit(Unit, nValue, sValue, Image=-1, BatteryLevel=255):
    if Image == -1:
        Image = Devices[Devices[Unit].Unit].Image
    UpdateDevice(Devices[Unit].Unit, nValue, sValue, Image)
    if BatteryLevel != 255:
        UpdateDeviceBatSig(Devices[Unit].Unit, BatteryLevel)

#UPDATE THE DEVICE
def UpdateDevice(Unit, nValue, sValue, Image, TimedOut=0, AlwaysUpdate=False):
    if Unit in Devices:
        if Devices[Unit].nValue != int(nValue) or Devices[Unit].sValue != str(sValue) or Devices[Unit].TimedOut != TimedOut or Devices[Unit].Image != Image or AlwaysUpdate:
            Domoticz.Debug("> Update unit {}: {} - {} - {}".format(Unit, Devices[Unit].Name, nValue, sValue))
            Devices[Unit].Update(nValue=int(nValue), sValue=str(sValue), Image=Image, TimedOut=TimedOut)
        else:
            Devices[Unit].Touch()

#UPDATE THE BATTERY LEVEL AND SIGNAL STRENGTH OF A DEVICE
def UpdateDeviceBatSig(Unit, BatteryLevel=255, SignalLevel=12):
    if Unit in Devices:
        if Devices[Unit].BatteryLevel != int(BatteryLevel) or Devices[Unit].SignalLevel != int(SignalLevel):
            Domoticz.Debug("> Update bat/sig unit {}: {} - {} - {} - {} - {}".format(
                Unit, Devices[Unit].Name, Devices[Unit].nValue, Devices[Unit].sValue, BatteryLevel, SignalLevel
            ))
            Devices[Unit].Update(nValue=Devices[Unit].nValue, sValue=Devices[Unit].sValue, BatteryLevel=int(BatteryLevel), SignalLevel=int(SignalLevel))
            Domoticz.Debug("> Updated bat/sig {}: {} - '{}' - {} - {}".format(
                Devices[Unit].Name, Devices[Unit].nValue, Devices[Unit].sValue, BatteryLevel, SignalLevel
            ))

#SET DEVICE ON TIMED-OUT (OR ALL DEVICES)
def TimeoutDevice(All, Unit=0):
    if All:
        for x in Devices:
            UpdateDevice(x, Devices[x].nValue, Devices[x].sValue, Devices[x].Image, TimedOut=_TIMEDOUT)
    else:
        UpdateDevice(Unit, Devices[Unit].nValue, Devices[Unit].sValue, Devices[Unit].Image, TimedOut=_TIMEDOUT)

#CREATE ALL THE DEVICES (USED)
def CreateDevicesUsed():
    if _UNIT_DIMMER not in Devices:
        name = "Cooling Fan"
        description = CreateDescription(name)
        Domoticz.Device(Name=name, Description=description, Unit=_UNIT_DIMMER, TypeName="Dimmer", Image=Images[_IMAGE].ID, Used=1).Create()

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
