# NEST Class to access the NEST Thermostat and Protect through the Google Account.
#
# Based on https://github.com/gboudreau/nest-api
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
import os.path
import sys
import datetime
import pytz
import tzlocal

where_map = { '00000000-0000-0000-0000-000100000000': 'Entryway',
              '00000000-0000-0000-0000-000100000001': 'Basement',
              '00000000-0000-0000-0000-000100000002': 'Hallway',
              '00000000-0000-0000-0000-000100000003': 'Den',
              '00000000-0000-0000-0000-000100000004': 'Attic', # Invisible in web UI
              '00000000-0000-0000-0000-000100000005': 'Master Bedroom',
              '00000000-0000-0000-0000-000100000006': 'Downstairs',
              '00000000-0000-0000-0000-000100000007': 'Garage', # Invisible in web UI
              '00000000-0000-0000-0000-000100000008': 'Kids Room',
              '00000000-0000-0000-0000-000100000009': 'Garage "Hallway"', # Invisible in web UI
              '00000000-0000-0000-0000-00010000000a': 'Kitchen',
              '00000000-0000-0000-0000-00010000000b': 'Family Room',
              '00000000-0000-0000-0000-00010000000c': 'Living Room',
              '00000000-0000-0000-0000-00010000000d': 'Bedroom',
              '00000000-0000-0000-0000-00010000000e': 'Office',
              '00000000-0000-0000-0000-00010000000f': 'Upstairs',
              '00000000-0000-0000-0000-000100000010': 'Dining Room'
            }

class Nest():

    def __init__(self, issue_token, cookie):
        self.issue_token = issue_token
        self.cookie = cookie
        self.nest_access_error = None
        self.nest_user_id = None
        self.nest_access_token = None
        self.access_token = None
        self.transport_url = None
        self.user = None
        self.cache_expiration_text = None
        self.cache_expiration = None
        self.access_token = None
        self.access_token_type = None
        self.id_token = None
        self.status = None
        self.device_list = []
        self.protect_list = []
        #self._ReadCache()

    def _ReadCache(self):
        if os.path.exists('nest.json'):
            try:
                with open('nest.json') as json_file:
                    data = json.load(json_file)
                    self.nest_user_id = data['user_id']
                    self.nest_access_token = data['access_token']
                    self.transport_url = data['transport_url']
                    self.user = data['user']
                    self.cache_expiration_text = data['cache_expiration'] #2019-11-23T11:16:51.640Z
                    self.cache_expiration = datetime.datetime.strptime(self.cache_expiration, '%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                pass

    def _WriteCache(self):
        try:
            with open('nest.json', 'w') as json_file:
                json.dump({ 'user_id': self_nest_user_id, 
                            'access_token': self.nest_access_token, 
                            'user': self.user, 
                            'transport_url': self.transport_url, 
                            'cache_expiration': self.cache_expiration_text
                          }, json_file)
        except:
            pass

    def _GetBearerTokenUsingGoogleCookiesIssue_token(self):
        self.nest_access_error = None
        url = self.issue_token
        headers = { 'Sec-Fetch-Mode': 'cors',
                    'User-Agent': 'Mozilla\/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit\/537.36 (KHTML, like Gecko) Chrome\/75.0.3770.100 Safari\/537.36',
                    'X-Requested-With': 'XmlHttpRequest',
                    'Referer': 'https://accounts.google.com/o/oauth2/iframe',
                    'Cookie': self.cookie
                  }
        result = requests.get(url, headers=headers)
        result = json.loads(result.text)
        if 'error' in result:
            self.nest_access_error = '%s (%s)' % (result['error'], result['detail'])
        elif 'access_token' in result and 'token_type' in result and 'id_token' in result:
            self.access_token = result['access_token']
            self.access_token_type = result['token_type']
            self.id_token = result['id_token']
 
    def _UseBearerTokenToGeAccessTokenAndUserId(self):
        url = 'https://nestauthproxyservice-pa.googleapis.com/v1/issue_jwt'
        data = { 'embed_google_oauth_access_token': True,
                 'expire_after': '3600s',
                 'google_oauth_access_token': self.access_token,
                 'policy_id': 'authproxy-oauth-policy'
               }
        headers = { 'Authorization': self.access_token_type + ' ' + self.access_token,
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
                    'X-Goog-API-Key': 'AIzaSyAdkSIMNc51XGNEAYWasX9UOWkS5P6sZE4', #Nest website's (public) API key
                    'Referer': 'https://home.nest.com'
                  }
        result = requests.post(url, data=json.dumps(data), headers=headers)
        result = json.loads(result.text)
        self.nest_user_id = result['claims']['subject']['nestId']['id']
        self.nest_access_token = result['jwt']
        self.cache_expiration_text = result['claims']['expirationTime']

    def _GetUser(self):
        url = 'https://home.nest.com/api/0.1/user/' + self.nest_user_id + '/app_launch'
        data = { 'known_bucket_types': ['user'],
                 'known_bucket_versions': []
               }
        headers = { 'X-nl-protocol-version': '1',
                    'X-nl-user-id': self.nest_user_id,
                    'Authorization': 'Basic ' + self.nest_access_token,
                    'Content-type': 'text/json'
                  }
        result = requests.post(url, data=json.dumps(data), headers=headers)
        result = json.loads(result.text)
        self.transport_url = result['service_urls']['urls']['transport_url']
        for bucket in result['updated_buckets']:
            if bucket['object_key'][:5] == 'user.':
                self.user = bucket['object_key']
                break
        if not self.user:
            self.user = 'user.'+self.nest_user_id

    def GetNestCredentials(self):
        #self._ReadCache()
        current_time = datetime.datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone())
        if  (self.cache_expiration is None) or (self.cache_expiration < current_time):
            self._GetBearerTokenUsingGoogleCookiesIssue_token()
            if not self.nest_access_error:
                self._UseBearerTokenToGeAccessTokenAndUserId()
                self._GetUser()
                self.cache_expiration = datetime.datetime.strptime(self.cache_expiration_text + current_time.strftime("%z"), '%Y-%m-%dT%H:%M:%S.%fZ%z')
                #self._WriteCache()
                return True
            else:
                #print(self.nest_access_error)
                return False

    def GetDevicesAndStatus(self):
        url = self.transport_url + '/v3/mobile/' + self.user
        headers = { 'X-nl-protocol-version': '1',
                    'X-nl-user-id': self.nest_user_id,
                    'Authorization': 'Basic ' + self.nest_access_token,
                  }
        result = requests.get(url, headers=headers)
        self.status = json.loads(result.text)

        #Thermostats
        del self.device_list[:]
        if 'user' in self.status and self.nest_user_id in self.status['user'] and 'structures' in self.status['user'][self.nest_user_id]:
            for structure in self.status['user'][self.nest_user_id]['structures']:
                structure_id = structure[10:]
                if 'structure' in self.status and structure_id in self.status['structure'] and 'devices' in self.status['structure'][structure_id]:
                    for device in self.status['structure'][structure_id]['devices']:
                        self.device_list.append(device[7:])

        #Protects
        del self.protect_list[:]
        if 'topaz' in self.status:
            for protect in self.status['topaz']:
                self.protect_list.append(str(protect))

    def GetDeviceInformation(self, device):
        structure = self.status['link'][device]['structure'][10:]
        info = { 'Name': str(self.status['structure'][structure]['name']),
                 'Away': self.status['structure'][structure]['away'],
                 'Target_temperature': self.status['shared'][device]['target_temperature'],
                 'Current_temperature': self.status['shared'][device]['current_temperature'],
                 'Temperature_scale':  self.status['device'][device]['temperature_scale'],
                 'Humidity': self.status['device'][device]['current_humidity'],
                 'Eco': self.status['device'][device]['eco']['mode'] != 'schedule', #if not 'schedule' --> in eco-mode
                 'Heating': self.status['shared'][device]['hvac_heater_state'],
                 'Where': where_map[self.status['device'][device]['where_id']]
               }
        return info

    def GetProtectInformation(self, device):
        info = { 'Smoke_status': self.status['topaz'][device]['smoke_status'],
                 'Serial_number': str(self.status['topaz'][device]['serial_number']),
                 'Co_previous_peak': str(self.status['topaz'][device]['co_previous_peak']),
                 'Where': where_map[self.status['topaz'][device]['spoken_where_id']]
               }
        return info

    def SetTemperature(self, device, target_temperature):
        url = self.transport_url + '/v2/put/shared.' + device
        data = { 'target_change_pending': True,
                 'target_temperature': target_temperature
               }
        headers = { 'X-nl-protocol-version': '1',
                    'X-nl-user-id': self.nest_user_id,
                    'Authorization': 'Basic ' + self.nest_access_token,
                    'Content-type': 'text/json'
                  }
        result = requests.post(url, data=json.dumps(data), headers=headers)
        if result.status_code == 200:
            return True
        else:
            return False

    def SetAway(self, device, is_away):
        url = self.transport_url + '/v2/put/structure.' + self.status['link'][device]['structure'][10:]
        data = { 'away': is_away,
                 'away_timestamp': round(datetime.datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone()).timestamp()),
                 'away_setter': 0
               }
        headers = { 'X-nl-protocol-version': '1',
                    'X-nl-user-id': self.nest_user_id,
                    'Authorization': 'Basic ' + self.nest_access_token,
                    'Content-type': 'text/json'
                  }
        result = requests.post(url, data=json.dumps(data), headers=headers)
        if result.status_code == 200:
            return True
        else:
            return False

if __name__ == "__main__":

    issue_token = 'XXXX'
    cookie = 'XXXX'
    thermostat = Nest(issue_token, cookie)
    while True:
        if thermostat.GetNestCredentials():
            thermostat.GetDevicesAndStatus()
            for device in thermostat.device_list:
                info = thermostat.GetDeviceInformation(device)
                print(info)
                #thermostat.SetTemperature(device, float(info['Target_temperature']))
            for device in thermostat.protect_list:
                print(thermostat.GetProtectInformation(device))
        time.sleep(10)
