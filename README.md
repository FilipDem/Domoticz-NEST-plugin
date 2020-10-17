# Donation
It took me quite some effort to get the plugin available. Small contributions are welcome...

[![](https://www.paypalobjects.com/en_US/BE/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=AT4L7ST55JR4A)

# Domoticz-NEST-plugin
NEST Plugin for Domoticz using the Google account credentials.

This is a workaround solution for NEST Thermostats and NEST Protect devices in Domoticz.
It does not use any official API because of non-existance. NEST/Google announced them only to be available by end of 2020.

For the plugin you need to enter two values in the Domoticz hardware plugin settings: issue_token and cookies.
The values of issue_token and cookies are specific to your Google Account. 
To get them, follow these steps (only needs to be done once, as long as you stay logged into your Google Account).

* Open a Chrome browser tab in Incognito Mode (or clear your cache).
* Open Developer Tools (View/Developer/Developer Tools).
* Click on Network tab. Make sure Preserve Log is checked.
* In the Filter box, enter issueToken
* Go to https://home.nest.com, and click Sign in with Google. Log into your account.
* One network call (beginning with iframerpc) will appear in the Dev Tools window. Click on it.
* In the Headers tab, under General, copy the entire Request URL (beginning with https://accounts.google.com, ending with nest.com). This is your $issue_token.
* In the Filter box, enter oauth2/iframe
* Several network calls will appear in the Dev Tools window. Click on the last iframe call.
* In the Headers tab, under Request Headers, copy the entire cookie value (include the whole string which is several lines long and has many field/value pairs - do not include the Cookie: prefix). This is your $cookies; make sure all of it is on a single line.

If you have problems, it is recommended to test with the nest.py plugin outside Domoticz. It is developed in python3 (so use "python3 nest.py").
You copy the credentials (issue_token and cookie) in the variables of the main section: just replace the XXXXX by the your values. 
* issue_token = 'XXXXX'
* cookie = 'XXXXX'

Success!

# Important remark

The plugin works with threading because couldn't get it working with the plugin connection system.
Normally I check at "onStop" if the threads are not running anymore before stopping. I followed the recommendations on https://github.com/domoticz/domoticz/blob/development/plugins/examples/Mutli-Threaded.py. With the debug information, it shows that there are no threads running anymore. However, when "updating" the device in the "hardware" tab, it leads to problems with the plugin system and a REBOOT of the system is required.
