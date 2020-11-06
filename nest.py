# Nest Class to access the Nest Thermostat and Protect through the Google Account.
#
# Based on https://github.com/gboudreau/nest-api
#
# Author: Filip Demaertelaere
# Extended by: Mark Ruys
#
# The values of issue_token and cookies are specific to your Google Account.
# To get them, follow these steps (only needs to be done once, as long as you stay logged into your Google Account).
#
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

import requests
import json
import time
from datetime import datetime
import pytz
import tzlocal

try:
    import Domoticz
    def log(msg=""):
        Domoticz.Debug(">> {}".format(msg))
except:
    def log(msg=""):
        print(msg)

class Nest():

    USER_AGENT = 'Domoticz Nest/1.0'
    REQUEST_TIMEOUT = 10.0

    def __init__(self, issue_token, cookie):
        self._issue_token = issue_token
        self._cookie = cookie
        self._access_token = None
        self._access_token_type = None
        self._nest_user_id = None
        self._nest_access_token = None
        self._transport_url = None
        self._user = None
        self._cache_expiration_text = None
        self._cache_expiration = None
        self._id_token = None
        self._status = None
        self._running = True
        self._nest_access_error = None
        #self._ReadCache()
        self.device_list = []
        self.protect_list = []
        self.where_map = {}

    def terminate(self):
        self._running = False

#     def _ReadCache(self):
#         if os.path.exists('nest.json'):
#             try:
#                 with open('nest.json') as json_file:
#                     data = json.load(json_file)
#                     self._nest_user_id = data['user_id']
#                     self._nest_access_token = data['access_token']
#                     self._transport_url = data['transport_url']
#                     self._user = data['user']
#                     self._cache_expiration_text = data['cache_expiration'] #2019-11-23T11:16:51.640Z
#                     self._cache_expiration = datetime.strptime(self._cache_expiration, '%Y-%m-%dT%H:%M:%S.%fZ')
#             except:
#                 pass

#     def _WriteCache(self):
#         try:
#             with open('nest.json', 'w') as json_file:
#                 json.dump({ 'user_id': self_nest_user_id,
#                             'access_token': self._nest_access_token,
#                             'user': self._user,
#                             'transport_url': self._transport_url,
#                             'cache_expiration': self._cache_expiration_text
#                           }, json_file)
#         except:
#             pass

    def _GetBearerTokenUsingGoogleCookiesIssue_token(self):
        if not self._running:
            return False

        url = self._issue_token
        headers = {
            'Sec-Fetch-Mode': 'cors',
            'User-Agent': self.USER_AGENT,
            'X-Requested-With': 'XmlHttpRequest',
            'Referer': 'https://accounts.google.com/o/oauth2/iframe',
            'Cookie': self._cookie,
        }
        try:
            request = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
            request.raise_for_status()
            result = request.json()
            if 'error' in result and 'detail' in result:
                if result['error'] == 'USER_LOGGED_OUT':
                    self._nest_access_error = 'API returned error: {}'.format(result['detail'])
                else:
                    self._nest_access_error = 'Invalid IssueToken/Cookie: %s (%s)' % (result['error'], result['detail'])
            elif 'access_token' in result and 'token_type' in result and 'id_token' in result:
                self._access_token = result['access_token']
                self._access_token_type = result['token_type']
                self._id_token = result['id_token']
                self._nest_access_error = None
                log("Got bearer token")
                return True

        except requests.exceptions.Timeout as e:
            self._nest_access_error = 'API request timed out'
        except requests.exceptions.ConnectionError as e:
            self._nest_access_error = 'Connection error API request'
        except requests.exceptions.HTTPError as e:
            self._nest_access_error = 'API request failed (status {})'.format(e.response.status_code)
        except json.JSONDecodeError as e:
            self._nest_access_error = 'Invalid API response'
        return False

    def _UseBearerTokenToGetAccessTokenAndUserId(self):
        url = 'https://nestauthproxyservice-pa.googleapis.com/v1/issue_jwt'
        data = {
            'embed_google_oauth_access_token': True,
             'expire_after': '3600s',
             'google_oauth_access_token': self._access_token,
             'policy_id': 'authproxy-oauth-policy',
        }
        headers = {
            'Authorization': self._access_token_type + ' ' + self._access_token,
            'User-Agent': self.USER_AGENT,
            'X-Goog-API-Key': 'AIzaSyAdkSIMNc51XGNEAYWasX9UOWkS5P6sZE4', #Nest website's (public) API key
            'Referer': 'https://home.nest.com',
        }
        request = self.PostMessageWithRetries(url, data, headers=headers, retries=2)
        if request is None:
            return False

        result = request.json()
        self._nest_user_id = result['claims']['subject']['nestId']['id']
        self._nest_access_token = result['jwt']
        self._cache_expiration_text = result['claims']['expirationTime']
        log("Got access token and user id")
        return True

    def _GetUser(self):
        url = 'https://home.nest.com/api/0.1/user/' + self._nest_user_id + '/app_launch'
        data = {
            'known_bucket_types': [ 'user' ],
            'known_bucket_versions': [],
        }
        request = self.PostMessageWithRetries(url, data, retries=2)
        if request is None:
            return False

        result = request.json()
        self._transport_url = result['service_urls']['urls']['transport_url']

        for bucket in result['updated_buckets']:
            if bucket['object_key'][:5] == 'user.':
                self._user = bucket['object_key']
                break
        if not self._user:
            self._user = 'user.' + self._nest_user_id

        log("Got user")
        return True

    def UpdateDevices(self):
        self._nest_access_error = None
        if self.GetNestCredentials():
            return self.GetDevicesAndStatus()
        else:
            return False

    def GetAccessError(self):
        if not self._nest_access_error:
            return 'All good'
        return self._nest_access_error

    def GetNestCredentials(self):
        #self._ReadCache()
        current_time = datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone())

        if self._cache_expiration is not None and self._cache_expiration > current_time:
            return True

        if not self._GetBearerTokenUsingGoogleCookiesIssue_token():
            return False
        if not self._UseBearerTokenToGetAccessTokenAndUserId():
            return False
        if not self._GetUser():
            return False

        self._cache_expiration = datetime.strptime(self._cache_expiration_text + current_time.strftime("%z"), '%Y-%m-%dT%H:%M:%S.%fZ%z')
        #self._WriteCache()
        return True

    def GetDevicesAndStatus(self):
        if self._running:
            url = self._transport_url + '/v3/mobile/' + self._user
            headers = {
                'X-nl-protocol-version': '1',
                'X-nl-user-id': self._nest_user_id,
                'Authorization': 'Basic ' + self._nest_access_token,
                'User-Agent': self.USER_AGENT,
            }
            try:
                request = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
            except requests.exceptions.Timeout as e:
                self._nest_access_error = 'Connection timeout'
                return False

            if request.status_code == 200:
                self._status = request.json()

#                 for key in self._status:
#                 for key in ['user', 'structure']:
#                     log("{}: {}".format(key, json.dumps(self._status[key])))
#                 log(json.dumps(self._status))

                #Thermostats
                try:
                    self.where_map = {}
                    self.device_list = []
                    for structure in self._status['user'][self._nest_user_id]['structures']:
                        structure_id = structure[10:]
                        self.where_map.update({
                            where['where_id'] : where['name']
                            for where in self._status['where'][structure_id]['wheres']
                        })
                        self.device_list += [ device[7:] for device in self._status['structure'][structure_id]['devices'] ]
                except:
                    pass

                #Protects
                if 'topaz' in self._status:
                    self.protect_list = [ str(protect) for protect in self._status['topaz'] ]

                log("Got devices and status")
                return True

            self._nest_access_error = 'Error getting device information (http status {})'.format(request.status_code)
        return False

    def GetDeviceInformation(self, device):
        structure = self._status['link'][device]['structure'][10:]
        info = {
            'Name': str(self._status['structure'][structure]['name']),
            'Away': self._status['structure'][structure]['away'],
            'Target_temperature': self._status['shared'][device]['target_temperature'],
            'Current_temperature': self._status['shared'][device]['current_temperature'],
            'Temperature_scale':  self._status['device'][device]['temperature_scale'],
            'Humidity': self._status['device'][device]['current_humidity'],
            'Eco': self._status['device'][device]['eco']['mode'] != 'schedule', #if not 'schedule' --> in eco-mode
            'Heating': self._status['shared'][device]['hvac_heater_state'],
            'Target_mode': self._status['shared'][device]['target_temperature_type'],
            'Target_temperature_low': self._status['shared'][device]['target_temperature_low'],
            'Target_temperature_high': self._status['shared'][device]['target_temperature_high'],
            'Where': self.where_map[self._status['device'][device]['where_id']],
        }
        return info

    def GetProtectInformation(self, device):
        #log(self._status['topaz'][device])
        info = {
            'Smoke_status': self._status['topaz'][device]['smoke_status'],
            'Serial_number': str(self._status['topaz'][device]['serial_number']),
            'Co_previous_peak': str(self._status['topaz'][device]['co_previous_peak']),
            'Where': self.where_map[self._status['topaz'][device]['spoken_where_id']],
            'Battery_low': str(self._status['topaz'][device]['battery_health_state']),
            'Battery_level': str(self._status['topaz'][device]['battery_level']),
        }
        return info

    def SetThermostat(self, device, mode): #False = set thermostat off
        url = self._transport_url + '/v2/put/shared.' + device
        data = {
            'target_change_pending': True,
            'target_temperature_type': mode,
        }
        return self.UpdateNest(url, data, "Thermostat set")

    def SetTemperature(self, device, target_temperature):
        url = self._transport_url + '/v2/put/shared.' + device
        data = {
            'target_change_pending': True,
            'target_temperature': target_temperature,
        }
        return self.UpdateNest(url, data, "Temperature set")

    def SetAway(self, device, is_away, eco_when_away=True):
        url = self._transport_url + '/v2/put/structure.' + self._status['link'][device]['structure'][10:]
        away_timestamp = datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone()).timestamp()
        data = {
            'away': is_away,
            'away_timestamp': round(away_timestamp),
            'away_setter': 0,
        }
        if self.UpdateNest(url, data, "Away set"):
            if is_away and eco_when_away:
                self.SetEco(device, 'manual-eco')
            return True
        else:
            return False

    def SetEco(self, device, mode): # mode equals 'manual-eco' or 'schedule'
        url = self._transport_url + '/v2/put/device.' + device
        mode_update_timestamp = datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone()).timestamp()
        data = {
            'eco': {
                'mode': mode,
                'mode_update_timestamp': round(mode_update_timestamp),
                'touched_by': 4,
            }
        }
        return self.UpdateNest(url, data, "Eco set")

    def UpdateNest(self, url, data, success_msg, retries=2):
        request = self.PostMessageWithRetries(url=url, data=data)
        if request is None:
            return False
        log(success_msg)
        return True

    def PostMessageWithRetries(self, url, data, headers=None, retries=1):
        if headers == None:
            headers = {
                'X-nl-protocol-version': '1',
                'X-nl-user-id': self._nest_user_id,
                'Authorization': 'Basic ' + self._nest_access_token,
                'Content-type': 'text/json',
                'User-Agent': self.USER_AGENT,
            }

        for i in range(retries):
            if not self._running:
                return None

            if i > 0:
                log("Retry API request")
            try:
                request = requests.post(url=url, json=data, headers=headers, timeout=self.REQUEST_TIMEOUT)
                if request.status_code == 200:
                    self._nest_access_error = None
                    return request
                self._nest_access_error = "API response status code {}".format(request.status_code)
                if request.status_code < 500:
                    break
            except requests.exceptions.Timeout as e:
                self._nest_access_error = 'Connection timeout'

            time.sleep(0.5)

        return None

if __name__ == "__main__":
    import os
    issue_token = os.environ.get('NEST_ISSUE_TOKEN')
    cookie = os.environ.get('NEST_COOKIE')
    if issue_token is None or cookie is None:
        log("Please set environment variables NEST_ISSUE_TOKEN and NEST_ISSUE_TOKEN")
        exit(1)
    thermostat = Nest(issue_token, cookie)
    if thermostat.UpdateDevices():
        for device in thermostat.device_list:
            info = thermostat.GetDeviceInformation(device)
            log(info)
            #log(thermostat.SetTemperature(device, float(info['Target_temperature'])))
            #log(thermostat.SetAway(device, info['Away']))
            #log(thermostat.SetEco(device, 'manual-eco'))
            #log(thermostat.SetThermostat(device, 'off'))
        for device in thermostat.protect_list:
            log(thermostat.GetProtectInformation(device))
    log(thermostat.GetAccessError())
