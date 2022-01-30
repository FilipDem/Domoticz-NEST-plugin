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
<plugin key="GoogleNest" name="Nest Thermostat/Protect Google" author="Filip Demaertelaere" version="2.3.0">
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
        You can now close the browser, but DO NOT LOGGED OUT from your Google Nest Account (logging out <br/>
        will invalidate the credentials).<br/>
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
import sys, os
major,minor,x,y,z = sys.version_info
sys.path.append('/usr/lib/python3/dist-packages')
sys.path.append('/usr/local/lib/python{}.{}/dist-packages'.format(major, minor))
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from domoticz_tools import *
import Domoticz
import nest
import threading
import queue
import time
import json

#DEFAULT IMAGE
_IMAGE_NEST_HEATING = 'GoogleNest Nest Heating'
_IMAGE_NEST_HEATING_OFF = 'GoogleNest Nest Heating Off'
_IMAGE_NEST_AWAY = 'GoogleNest Nest Away'
_IMAGE_NEST_ECO = 'GoogleNest Nest Eco'
_IMAGE_NEST_PROTECT = 'GoogleNest Nest Protect'

#DEVICE NAMES
_NEST_HEATING = 'Heating'
_NEST_ECO_MODE = 'Eco Mode'
_NEST_AWAY = 'Away'
_NEST_TEMP_HUM = 'Temp/Hum'
_NEST_HEATING_TEMP = 'Heating Temp'
_NEST_PROTECT = 'Protect'
_NEST_WIND = 'Wind'

################################################################################
# Start Plugin
################################################################################

class BasePlugin:

    def __init__(self):
        self.debug = DEBUG_OFF
        self.runAgain = MINUTE
        self.ErrorLevel = 0
        self.myNest = None
        self.round_temperature = 0
        self.wind_list = []
        self.tasksQueue = queue.Queue()
        self.tasksThread = threading.Thread(name='QueueThread', target=BasePlugin.handleTasks, args=(self,))

    def onStart(self):
        # Set debug level according to user setting
        self.debug = DEBUG_ON if Parameters['Mode6'] == 'Debug' else DEBUG_OFF
        Domoticz.Debugging(self.debug)
        if self.debug == DEBUG_ON:
            DumpConfigToLog(Parameters, Devices)

        # Read technical parameters
        try:
            config = None
            with open('./plugins/GoogleNest/GoogleNest.json') as json_file:
                config = json.load(json_file)
            self.round_temperature = config['RoundTemperature']
        except:
            pass

        # Create images if necessary
        if _IMAGE_NEST_AWAY not in Images:
            Domoticz.Image('Nest Away.zip').Create()
        if _IMAGE_NEST_ECO not in Images:
            Domoticz.Image('Nest Eco.zip').Create()
        if _IMAGE_NEST_HEATING not in Images:
            Domoticz.Image('Nest Heating.zip').Create()
        if _IMAGE_NEST_HEATING_OFF not in Images:
            Domoticz.Image('Nest Heating Off.zip').Create()
        if _IMAGE_NEST_PROTECT not in Images:
            Domoticz.Image('Nest Protect.zip').Create()
        Domoticz.Debug('> Images created')

        # Set all devices as timed out
        TimeoutDevice(Devices, All=True)

        # Create Nest instance
        if not Parameters['Mode1'].startswith('https://accounts.google.com'):
            Domoticz.Error('Hardware setting issue_token must start with https://accounts.google.com.')
        elif not Parameters['Mode1'].endswith('nest.com'):
            Domoticz.Error('Hardware setting issue_token must end with nest.com.')
        else:
            self.myNest = nest.Nest(Parameters['Mode1'], Parameters['Mode2'], float(Parameters['Mode5'].replace(',','.')))
            self.tasksThread.start()
            self.tasksQueue.put({'Action': 'StatusUpdate'})
            self.tasksQueue.put({'Action': 'OutsideWeather'})

        Domoticz.Debug('> Plugin started')

    def onStop(self):
        Domoticz.Debug('> onStop called')
        
        # Signal queue thread to exit
        self.tasksQueue.put(None)
        self.tasksQueue.join()

        # Wait until queue thread has exited
        Domoticz.Debug('Threads still active: {} (should be 1)'.format(threading.active_count()))
        endTime = time.time() + 70
        while (threading.active_count() > 1) and (time.time() < endTime):
            for thread in threading.enumerate():
                if thread.name != threading.current_thread().name:
                    Domoticz.Debug('Thread {} is still running, waiting otherwise Domoticz will abort on plugin exit.'.format(thread.name))
            time.sleep(1.0)

        Domoticz.Debug('> Plugin stopped')

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug('> onConnect called, ignored')

    def onMessage(self, Connection, Data):
        Domoticz.Debug('> onMessage called, ignored')

    def onCommand(self, Unit, Command, Level, Hue):            
        Domoticz.Debug('> onCommand called: Unit: {} - Command: {} - Level {} - Hue: {}'.format(Unit, Command, Level, Hue))

        for device in self.myNest.device_list:
            info = self.myNest.GetThermostatInformation(device)
            Domoticz.Debug('> {} - {}'.format(info['Where'], Devices[Unit].Name))

            # Set heating temperature
            if DeviceNameBelongsToUnit(info['Where'] + ' ' + _NEST_HEATING_TEMP, Unit):
                self.tasksQueue.put({'Action': 'SetHeatingTemp', 'Device': device, 'Value': Level})
            
            # Set Away status
            elif DeviceNameBelongsToUnit(_NEST_AWAY, Unit):
                self.tasksQueue.put({'Action': 'SetAway', 'Device': device, 'Value': Command})
            
            # Set Eco mode
            elif DeviceNameBelongsToUnit(info['Where'] + ' ' + _NEST_ECO_MODE, Unit):
                self.tasksQueue.put({'Action': 'SetEcoMode', 'Device': device, 'Value': Command})

            # Set Heating
            elif DeviceNameBelongsToUnit(info['Where'] + ' ' + _NEST_HEATING, Unit):
                self.tasksQueue.put({'Action': 'SetHeating', 'Device': device, 'Value': Command})

        Domoticz.Debug('Processed {} to {} for unit {}'.format(Command, Level, Unit))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug('> Notification: {}, {}, {}, {}, {}, {}, {}'.format(
            Name, Subject, Text, Status, Priority, Sound, ImageFile
        ))

    def onDisconnect(self, Connection):
        Domoticz.Debug('> onDisconnect called, ignored')

    def onHeartbeat(self):
        self.runAgain -= 1
        if self.runAgain <= 0:

            # Get Nest Update
            self.tasksQueue.put({'Action': 'StatusUpdate'})
            self.tasksQueue.put({'Action': 'OutsideWeather'})
            if self.ErrorLevel == 5:
                TimeoutDevice(Devices, All=True)
                Domoticz.Error('ERRORLEVEL=5 Unable to get update data from Nest (last error: {}).'.format(self.myNest._nest_access_error))

            # Run again following the period in the settings
            self.runAgain = MINUTE * float(Parameters['Mode5'].replace(',','.'))

    def handleTasks(self):
        try:
            Domoticz.Debug('> Entering tasks handler')
            while True:
                task = self.tasksQueue.get(block=True)
                if task is None:
                    Domoticz.Debug('> Exiting task handler')
                    try:
                        self.myNest.terminate()
                    except AttributeError:
                        pass
                    self.tasksQueue.task_done()
                    break

                Domoticz.Debug('> Handling task: {}.'.format(task['Action']))
                DeviceUpdate = False
                DeviceUpdateRequested = False
                if task['Action'] == 'StatusUpdate':
                    DeviceUpdateRequested = True
                    DeviceUpdate = self.myNest.UpdateDevices()
                        
                elif task['Action'] == 'SetHeatingTemp':
                    DeviceUpdateRequested = True
                    DeviceUpdate = self.myNest.SetTemperature(task['Device'], task['Value']) and self.myNest.UpdateDevices()
                    
                elif task['Action'] == 'SetAway':
                    DeviceUpdateRequested = True
                    Away = True if task['Value'] == 'On' else False
                    DeviceUpdate = self.myNest.SetAway(task['Device'], Away) and self.myNest.UpdateDevices()

                elif task['Action'] == 'SetEcoMode':
                    DeviceUpdateRequested = True
                    Eco = 'manual-eco' if task['Value'] == 'On' else 'schedule'
                    DeviceUpdate = self.myNest.SetEco(task['Device'], Eco) and self.myNest.UpdateDevices()

                elif task['Action'] == 'SetHeating':
                    DeviceUpdateRequested = True
                    Heat = 'heat' if task['Value'] == 'On' else 'off'
                    DeviceUpdate = self.myNest.SetThermostat(task['Device'], Heat) and self.myNest.UpdateDevices()

                elif task['Action'] == 'OutsideWeather':
                    WeatherUpdate = self.myNest.GetOutsideTempHum()
                    if WeatherUpdate:
                        updated_units = self.updateWeather(WeatherUpdate)
                        self.ErrorLevel = 0
                        Domoticz.Debug('> Updated {} units for weather.'.format(updated_units))
                    else:
                        self.ErrorLevel += 1
                        Domoticz.Debug('Unable to get weather data from Nest (last error: {}).'.format(self.myNest._nest_access_error))

                else:
                    Domoticz.Error('> TaskHandler: unknown action code {}'.format(task['Action']))
                    DeviceUpdate = self.myNest.UpdateDevices()

                if DeviceUpdate:
                    updated_units = self.updateNestInfo() + self.updateThermostats() + self.updateProtects()
                    self.ErrorLevel = 0
                    Domoticz.Debug('> Updated {} units for {} device(s)'.format(updated_units, len(self.myNest.device_list) + len(self.myNest.protect_list)))
                else:
                    if DeviceUpdateRequested:
                        self.ErrorLevel += 1
                        Domoticz.Debug('Unable to get update data from Nest (last error: {}).'.format(self.myNest._nest_access_error))

                self.tasksQueue.task_done()
                Domoticz.Debug('> Finished handling task: {}.'.format(task['Action']))

        except Exception as err:
            self.tasksQueue.task_done()
            Domoticz.Error('> General error TaskHandler: {}'.format(err))

    def updateProtects(self):
        updated_units = 0
        for nest_device in self.myNest.protect_list:
            info = self.myNest.GetProtectInformation(nest_device)
            Domoticz.Debug('> {}'.format(json.dumps(info)))
            #Create device if required and allowed
            device_name = info['Where'] + ' ' + _NEST_PROTECT
            unit = FindUnitByNestName(device_name)
            if not unit:
                unit = GetNextFreeUnit(Devices)
                description = CreateDescription(device_name)
                Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=5, Image=Images[_IMAGE_NEST_PROTECT].ID, Used=1).Create()
            if info['Smoke_status'] or info['Co_status'] or info['Heat_status'] :
                UpdateDevice(Devices, unit, 1, 1, BatteryLevel=int(int(info['Battery_level'])/100))
            else:
                UpdateDevice(Devices, unit, 0, 0, BatteryLevel=int(int(info['Battery_level'])/100))
            updated_units += 1
        return updated_units

    def updateThermostats(self):
        updated_units = 0
        for nest_device in self.myNest.device_list:
            info = self.myNest.GetThermostatInformation(nest_device)
            Domoticz.Debug('> {}'.format(json.dumps(info)))

            #Update NEST HEATING and create device if required
            device_name = info['Where'] + ' ' + _NEST_HEATING
            unit = FindUnitByNestName(device_name)
            if not unit:
                unit = GetNextFreeUnit(Devices)
                description = CreateDescription(device_name)
                Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_HEATING].ID, Used=1).Create()
            if info['Heating']:
                UpdateDevice(Devices, unit, 1, 1, Images[_IMAGE_NEST_HEATING].ID)
            else:
                #Update NEST HEATING icon off or on
                if info['Target_mode'] == 'off':
                    UpdateDevice(Devices, unit, 0, 0, Images[_IMAGE_NEST_HEATING_OFF].ID)
                else:
                    UpdateDevice(Devices, unit, 0, 0, Images[_IMAGE_NEST_HEATING].ID)
            updated_units += 1

            #Update NEST ECO MODE and create device if required
            device_name = info['Where'] + ' ' + _NEST_ECO_MODE
            unit = FindUnitByNestName(device_name)
            if not unit:
                unit = GetNextFreeUnit(Devices)
                description = CreateDescription(device_name)
                Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_ECO].ID, Used=1).Create()
            if info['Eco']:
                UpdateDevice(Devices, unit, 1, 1)
            else:
                UpdateDevice(Devices, unit, 0, 0)
            updated_units += 1

            #Update NEST TEMP/HUMIDITY and create device if required
            device_name = info['Where'] + ' ' + _NEST_TEMP_HUM
            unit = FindUnitByNestName(device_name)
            if not unit:
                unit = GetNextFreeUnit(Devices)
                description = CreateDescription(device_name)
                Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=82, Subtype=1, Switchtype=0, Used=1).Create()
            if self.round_temperature:
                temperature = round(info['Current_temperature'] * 2) / 2
            else:
                temperature = info['Current_temperature']
            UpdateDevice(Devices, unit, 0, '%.1f;%.0f;0'%(temperature, info['Humidity']))
            updated_units += 1

            #Update NEST HEATING TEMPERATURE and create device if required
            device_name = info['Where'] + ' ' + _NEST_HEATING_TEMP
            unit = FindUnitByNestName(device_name)
            if not unit:
                unit = GetNextFreeUnit(Devices)
                description = CreateDescription(device_name)
                Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=242, Subtype=1, Switchtype=0, TypeName=info['Temperature_scale'], Used=1).Create()
            UpdateDevice(Devices, unit, info['Target_temperature'], info['Target_temperature'])
            updated_units += 1
            
            #Update device for the auto-away of the thermostat
            device_name = info['Where'] + ' ' + _NEST_AWAY
            unit = FindUnitByNestName(device_name)
            if not unit:
                unit = GetNextFreeUnit(Devices)
                description = CreateDescription(device_name)
                Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_AWAY].ID, Used=0).Create()
            #Auto_away<0=disabled; Auto_away==0=enabled+home; Auto_away>0=enabled+away
            if info['Auto_away'] > 0:
                UpdateDevice(Devices, unit, 1, 1)
            elif info['Auto_away'] == 0:
                UpdateDevice(Devices, unit, 0, 0)
            updated_units += 1
                  
        return updated_units

    def updateNestInfo(self):
        updated_units = 0
        info = self.myNest.GetNestInformation()
        Domoticz.Debug('> {}'.format(json.dumps(info)))

        #Update NEST AWAY and create device if required
        device_name = _NEST_AWAY
        unit = FindUnitByNestName(device_name)
        if not unit:
            unit = GetNextFreeUnit(Devices)
            description = CreateDescription(device_name)
            Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=244, Subtype=73, Switchtype=0, Image=Images[_IMAGE_NEST_AWAY].ID, Used=1).Create()
        if info['Away']:
            UpdateDevice(Devices, unit, 1, 1)
        else:
            UpdateDevice(Devices, unit, 0, 0)
        updated_units += 1
        return updated_units

    def updateWeather(self, weather_info):
        updated_units = 0
        Domoticz.Debug('> {}'.format(json.dumps(weather_info)))

        #update Temperature/Humidity and create device if required
        device_name = '{} {}'.format(weather_info['City'], _NEST_TEMP_HUM)
        unit = FindUnitByNestName(device_name)
        if not unit:
            unit = GetNextFreeUnit(Devices)
            description = CreateDescription(device_name)
            Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=82, Subtype=1, Switchtype=0, Used=1).Create()
        UpdateDevice(Devices, unit, 0, '%.1f;%.0f;0'%(weather_info['Current_temperature'], weather_info['Current_humidity']))
        updated_units += 1

        #update Wind and create device if required
        device_name = '{} {}'.format(weather_info['City'], _NEST_WIND)
        unit = FindUnitByNestName(device_name)
        if not unit:
            unit = GetNextFreeUnit(Devices)
            description = CreateDescription(device_name)
            Domoticz.Device(Unit=unit, Name=device_name, Description=description, Type=86, Subtype=4, Switchtype=0, Used=1).Create()
        wind_km = 1.609344 * weather_info['Current_wind']
        directions = {'N':0, 'NNE':22.5, 'NE':45, 'ENE':67.5, 'E':90, 'ESE':112.5, 'SE':135,'SSE':157.5, 'S':180, 'SSW':202.5, 'SW':225, 'WSW':247.5, 'W':270, 'WNW':292.5, 'NW':315, 'NNW':337.5, 'N':0, 'North':0, 'East':90, 'West':270, 'South':180}
        wind_chill = 13.12 + (0.6215 * weather_info['Current_temperature']) + (-11.37 * wind_km ** 0.16) + (0.3965 * weather_info['Current_temperature'] * wind_km ** 0.16)
        if len(self.wind_list)>10:
            self.wind_list.pop(0)
        self.wind_list.append(wind_km)
        UpdateDevice(Devices, unit, 0, '%.1f;%s;%d;%.1f;%.1f;%.1f'%(directions[weather_info['Wind_direction']], weather_info['Wind_direction'], 10000/3600*wind_km, 10000/3600*max(self.wind_list), weather_info['Current_temperature'], wind_chill))
        updated_units += 1

        return updated_units
        
    
    
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
# Specific helper functions
################################################################################

def DeviceNameBelongsToUnit(device_name, Unit):
    needle = '[{}]'.format(device_name).lower()
    return needle in Devices[Unit].Description.lower()

def CreateDescription(tag):
    return 'Do not remove: [{}]'.format(tag)

def FindUnitByNestName(device_name):
    for Unit in Devices:
        if DeviceNameBelongsToUnit(device_name, Unit):
            return Unit

    # For backwards compatibility, scan for device names ending in device_name
    for Unit in Devices:
        Domoticz.Debug('Check {} ends with {}'.format(Devices[Unit].Name, device_name))
        if Devices[Unit].Name.lower().endswith(device_name.lower()):
            descriptions = [] if Devices[Unit].Description == '' else [ Devices[Unit].Description ]
            descriptions += [ CreateDescription(device_name) ]
            Devices[Unit].Update(Description='; '.join(descriptions), nValue=Devices[Unit].nValue, sValue=Devices[Unit].sValue)
            Domoticz.Debug('Updated description to {}'.format('; '.join(descriptions)))
            return Unit
    return None
