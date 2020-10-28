# Donation
It took me quite some effort to get the plugin available. Small contributions are welcome...

[![](https://www.paypalobjects.com/en_US/BE/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=AT4L7ST55JR4A)

# Domoticz-NEST-plugin
NEST Plugin for Domoticz using the Google account credentials.

This is a workaround solution for NEST Thermostats and NEST Protect devices in Domoticz.
It does not use any official API because of non-existance. NEST/Google announced them only to be available by end of 2020.

The plugin creates the following devices: Away, Eco-mode, Heating, Temperature/Humidity, Heating temperature, Nest Protect.

## Installation (linux)
Follow this procedure to install the plugin.
* Go to "~/Domoticz/plugins" with the command ```cd ~/Domoticz/plugins```
* Create directory "GoogleNest" with the command ```mkdir GoogleNest```
* Copy all the files from github in the created directory
* Be sure the following python3 libraries are installed: requests, pytz and tzlocal
   * use ```pip3 list``` to verify if the libraries are installed
   * to install the missing libraries: ```sudo pip3 install <library>```
* Restart Domoticz with ```sudo systemctl restart domoticz.service```

## Adding NEST to Domoticz
In the Setup - Hardware, 
   * add the *Type* (dropdown) **Nest Thermostat/Protect Google**
   * give the device a *Name* (eg **Nest**)
   * for the fields *issue_token* and *cookie*, follow the guidance in the section hereafter (Configuration)
   * for the settings *minutes between updates*, recommendation is to avoid below 2 minutes
   
## Configuration
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

## Device creation
After the start of the plugin the devices will be automatically created for: Heating (on/off), Eco mode (on/off), Away (on/off), Temp/hum (temperature and humidity), Heating Temp (thermostat temperature), Protect (on/off).
The names of the devices are created automatically based on the location settings of your Nest with: <name of the hardware> - <location> <type of switch>
   * <name of the hardware>: name as entered in the Setup - Hardware screen
   * <location>: as set up in the nest account, some possible values 'Entryway', 'Kitchen', 'Living Room', ...
   * <type of switch>: 'Heating', 'Eco mode', 'Away', 'Temp/Hum', 'Heating Temp', 'Protect'

Success!

**Don't forget a small gift by using the donation button...**
