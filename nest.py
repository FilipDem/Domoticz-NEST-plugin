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
      
    def terminate(self): 
        self._running = False
        
    def _ReadCache(self):
        if os.path.exists('nest.json'):
            try:
                with open('nest.json') as json_file:
                    data = json.load(json_file)
                    self._nest_user_id = data['user_id']
                    self._nest_access_token = data['access_token']
                    self._transport_url = data['transport_url']
                    self._user = data['user']
                    self._cache_expiration_text = data['cache_expiration'] #2019-11-23T11:16:51.640Z
                    self._cache_expiration = datetime.datetime.strptime(self._cache_expiration, '%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                pass

    def _WriteCache(self):
        try:
            with open('nest.json', 'w') as json_file:
                json.dump({ 'user_id': self_nest_user_id, 
                            'access_token': self._nest_access_token, 
                            'user': self._user, 
                            'transport_url': self._transport_url, 
                            'cache_expiration': self._cache_expiration_text
                          }, json_file)
        except:
            pass

    def _GetBearerTokenUsingGoogleCookiesIssue_token(self):
        if self._running:
            self._nest_access_error = None
            url = self._issue_token
            headers = { 'Sec-Fetch-Mode': 'cors',
                        'User-Agent': 'Mozilla\/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit\/537.36 (KHTML, like Gecko) Chrome\/75.0.3770.100 Safari\/537.36',
                        'X-Requested-With': 'XmlHttpRequest',
                        'Referer': 'https://accounts.google.com/o/oauth2/iframe',
                        'Cookie': self._cookie
                      }
            try:
                result = requests.get(url, headers=headers)
            except:
                self._nest_access_error = 'Invalid IssueToken/Cookie.'
                return False
               
            if result.status_code == 200:
                result = json.loads(result.text)
                if 'error' in result:
                    self._nest_access_error = 'Invalid IssueToken/Cookie: %s (%s)' % (result['error'], result['detail'])
                elif 'access_token' in result and 'token_type' in result and 'id_token' in result:
                    self._access_token = result['access_token']
                    self._access_token_type = result['token_type']
                    self._id_token = result['id_token']
                    return True
            else:
                result = json.loads(result.text)
                self._nest_access_error = 'Invalid IssueToken/Cookie: %s (%s)' % (result['error'], result['error_description'])
            return False
 
    def _UseBearerTokenToGetAccessTokenAndUserId(self):
        if self._running:
            url = 'https://nestauthproxyservice-pa.googleapis.com/v1/issue_jwt'
            data = { 'embed_google_oauth_access_token': True,
                     'expire_after': '3600s',
                     'google_oauth_access_token': self._access_token,
                     'policy_id': 'authproxy-oauth-policy'
                   }
            headers = { 'Authorization': self._access_token_type + ' ' + self._access_token,
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
                        'X-Goog-API-Key': 'AIzaSyAdkSIMNc51XGNEAYWasX9UOWkS5P6sZE4', #Nest website's (public) API key
                        'Referer': 'https://home.nest.com'
                      }
            result = requests.post(url, data=json.dumps(data), headers=headers)
            if result.status_code == 200:
                result = json.loads(result.text)
                self._nest_user_id = result['claims']['subject']['nestId']['id']
                self._nest_access_token = result['jwt']
                self._cache_expiration_text = result['claims']['expirationTime']
                return True

            self._nest_access_error = 'Invalid IssueToken/Cookie: Problem to get AccessToken and UserId.'
            return False

    def _GetUser(self):
        if self._running:
            url = 'https://home.nest.com/api/0.1/user/' + self._nest_user_id + '/app_launch'
            data = { 'known_bucket_types': ['user'],
                     'known_bucket_versions': []
                   }
            headers = { 'X-nl-protocol-version': '1',
                        'X-nl-user-id': self._nest_user_id,
                        'Authorization': 'Basic ' + self._nest_access_token,
                        'Content-type': 'text/json'
                      }
            result = requests.post(url, data=json.dumps(data), headers=headers)
            if result.status_code == 200:
                result = json.loads(result.text)
                self._transport_url = result['service_urls']['urls']['transport_url']
                for bucket in result['updated_buckets']:
                    if bucket['object_key'][:5] == 'user.':
                        self._user = bucket['object_key']
                        break
                if not self._user:
                    self._user = 'user.'+self._nest_user_id
                return True

            self._nest_access_error = 'Invalid IssueToken/Cookie: Problem to get User.'
            return False

    def UpdateDevices(self):
        if not self._nest_access_error:
            if self.GetNestCredentials():
                return self.GetDevicesAndStatus()
        return False

    def GetAccessError(self):
        if not self._nest_access_error:
            return 'No error identified.'
        return self._nest_access_error

    def GetNestCredentials(self):
        #self._ReadCache()
        current_time = datetime.datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone())
        if  (self._cache_expiration is None) or (self._cache_expiration < current_time):
            if self._GetBearerTokenUsingGoogleCookiesIssue_token():
                if self._UseBearerTokenToGetAccessTokenAndUserId():
                    if self._GetUser():
                        self._cache_expiration = datetime.datetime.strptime(self._cache_expiration_text + current_time.strftime("%z"), '%Y-%m-%dT%H:%M:%S.%fZ%z')
                        #self._WriteCache()
                        return True
            #print(self._nest_access_error)
            return False
        #Cache not expired
        return True

    def GetDevicesAndStatus(self):
        if self._running:
            url = self._transport_url + '/v3/mobile/' + self._user
            headers = { 'X-nl-protocol-version': '1',
                        'X-nl-user-id': self._nest_user_id,
                        'Authorization': 'Basic ' + self._nest_access_token,
                      }
            result = requests.get(url, headers=headers)
            if result.status_code == 200:
                self._status = json.loads(result.text)

                #Thermostats
                del self.device_list[:]
                if 'user' in self._status and self._nest_user_id in self._status['user'] and 'structures' in self._status['user'][self._nest_user_id]:
                    for structure in self._status['user'][self._nest_user_id]['structures']:
                        structure_id = structure[10:]
                        if 'structure' in self._status and structure_id in self._status['structure'] and 'devices' in self._status['structure'][structure_id]:
                            for device in self._status['structure'][structure_id]['devices']:
                                self.device_list.append(device[7:])

                #Protects
                del self.protect_list[:]
                if 'topaz' in self._status:
                    for protect in self._status['topaz']:
                        self.protect_list.append(str(protect))
                
                #All OK
                return True
                
            self._nest_access_error = 'Error getting device information.'
            return False 

    def GetDeviceInformation(self, device):
        structure = self._status['link'][device]['structure'][10:]
        info = { 'Name': str(self._status['structure'][structure]['name']),
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
                 'Where': where_map[self._status['device'][device]['where_id']]
               }
        return info

    def GetProtectInformation(self, device):
        #print(self._status['topaz'][device])
        info = { 'Smoke_status': self._status['topaz'][device]['smoke_status'],
                 'Serial_number': str(self._status['topaz'][device]['serial_number']),
                 'Co_previous_peak': str(self._status['topaz'][device]['co_previous_peak']),
                 'Where': where_map[self._status['topaz'][device]['spoken_where_id']],
                 'Battery_low': str(self._status['topaz'][device]['battery_health_state']),
                 'Battery_level': str(self._status['topaz'][device]['battery_level'])
               }
        return info

    def SetThermostat(self, device, mode): #False = set thermostat off
        url = self._transport_url + '/v2/put/shared.' + device
        data = { 'target_change_pending': True,
                 'target_temperature_type': mode
               }
        return self.PostMessage(url, data)

    def SetTemperature(self, device, target_temperature):
        url = self._transport_url + '/v2/put/shared.' + device
        data = { 'target_change_pending': True,
                 'target_temperature': target_temperature
               }
        return self.PostMessage(url, data)

    def SetAway(self, device, is_away, eco_when_away=True):
        url = self._transport_url + '/v2/put/structure.' + self._status['link'][device]['structure'][10:]
        data = { 'away': is_away,
                 'away_timestamp': round(datetime.datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone()).timestamp()),
                 'away_setter': 0
               }
        if self.PostMessage(url, data):
            if is_away and eco_when_away:
                self.SetEco(device, 'manual-eco')
            return True
        else:
            return False

    def SetEco(self, device, mode): # mode equals 'manual-eco' or 'schedule'
        url = self._transport_url + '/v2/put/device.' + device
        data = {}
        data['eco'] = { 'mode': mode,
                        'mode_update_timestamp': round(datetime.datetime.now(pytz.timezone('utc')).astimezone(tzlocal.get_localzone()).timestamp()),
                        'touched_by': 4
                      }
        return self.PostMessage(url, data)

    def PostMessage(self, url, data):
        headers = { 'X-nl-protocol-version': '1',
                    'X-nl-user-id': self._nest_user_id,
                    'Authorization': 'Basic ' + self._nest_access_token,
                    'Content-type': 'text/json'
                  }
        result = requests.post(url, data=json.dumps(data), headers=headers)
        if result.status_code == 200:
            return True
        else:
            return False

if __name__ == "__main__":

    issue_token = 'xxxx'
    cookie = 'yyyy'
    thermostat = Nest(issue_token, cookie)
    while True:
        print(thermostat.GetAccessError())
        if thermostat.UpdateDevices():
            for device in thermostat.device_list:
                info = thermostat.GetDeviceInformation(device)
                print(info)
                #print(thermostat.SetTemperature(device, float(info['Target_temperature'])))
                #print(thermostat.SetAway(device, info['Away']))
                #print(thermostat.SetEco(device, 'manual-eco'))
                #print(thermostat.SetThermostat(device, 'off'))
            for device in thermostat.protect_list:
                print(thermostat.GetProtectInformation(device))
        else:
            print(thermostat.GetAccessError())
        time.sleep(10)
