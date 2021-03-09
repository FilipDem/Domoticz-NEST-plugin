# Donation
It took me quite some effort to get the plugin available. Small contributions are welcome...

[![](https://www.paypalobjects.com/en_US/BE/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=AT4L7ST55JR4A)

# Domoticz-NEST-plugin
Nest plugin for Domoticz using the Google account credentials.

This is a workaround solution for Nest thermostats and Nest Protect devices in Domoticz. It does not use any official API because of non-existance. Nest/Google announced them only to be available by end of 2020. Nest Thermostat E (UK/EU version) is not supported.

The plugin creates the following devices: Away, Eco-mode, Heating, Temperature/Humidity, Heating temperature, and Nest Protect. From now on, the "Away"-device is not linked to the Thermostat devices. In the scenario with only Nest Protect devices, the "Away"-device will anyway be created and give the away-status. Read also the chapter "Migration".

## Installation (linux)
Follow this procedure to install the plugin.
* Go to "~/Domoticz/plugins" with the command ```cd ~/Domoticz/plugins```
* Create directory "GoogleNest" with the command ```mkdir GoogleNest```
* Copy all the files from github in the created directory
* Be sure the following python3 libraries are installed: requests, pytz and tzlocal
   * use ```pip3 list``` to verify if the libraries are installed
   * to install the missing libraries: ```sudo pip3 install <library>```
* Restart Domoticz with ```sudo systemctl restart domoticz.service```

## Adding Nest to Domoticz
In the Setup - Hardware, 
   * add the *Type* (dropdown) **Nest Thermostat/Protect Google**
   * give the device a *Name* (eg **Nest**)
   * for the fields *issue_token* and *cookie*, follow the guidance in the section hereafter (Configuration)
   * for the settings *minutes between updates*, recommendation is to avoid below 2 minutes

## Configuration
For the plugin you need to enter two values in the Domoticz hardware plugin settings: issue_token and cookies.
The values of issue_token and cookies are specific to your Google Account. To get them, follow these steps (only needs to be done once, as long as you stay logged into your Google Account):

* Open a Chrome browser tab in Incognito Mode (or clear your cache).
* Open Developer Tools (View/Developer/Developer Tools).
* Click on Network tab. Make sure Preserve Log is checked.
* In the Filter box, enter issueToken.
* Go to https://home.nest.com, and click Sign in with Google. Log into your account.
* One network call (beginning with iframerpc) will appear in the Dev Tools window. Click on it.
* In the Headers tab, under General, copy the entire Request URL (beginning with https://accounts.google.com, ending with nest.com). This is your $issue_token.
* In the Filter box, enter oauth2/iframe.
* Several network calls will appear in the Dev Tools window. Click on the last iframe call.
* In the Headers tab, under Request Headers, copy the entire cookie value (include the whole string which is several lines long and has many field/value pairs - do not include the Cookie: prefix). This is your $cookies; make sure all of it is on a single line.

If you have problems, it is recommended to test with the nest.py plugin outside Domoticz. It is developed in python3 (substitute the proper values for `xxx`):

```shell
export NEST_ISSUE_TOKEN='xxx'
export NEST_COOKIE='xxx'
python3 nest.py
```

## Device creation
After the start of the plugin the devices will be automatically created for: 

* Away (on/off)
* Heating (on/off)
* Eco mode (on/off)
* Temp/hum (temperature and humidity)
* Heating Temp (thermostat temperature)
* Protect (on/off)

The names of the devices are created automatically based on the location settings of your Nest devices with *name_of_the_hardware* - *location type_of_switch*, except for the "Away"-device.

   * name_of_the_hardware: name as entered in the Setup - Hardware screen
   * location: as set up in the nest account, some possible values 'Entryway', 'Kitchen', 'Living Room', ...
   * type_of_switch: 'Heating', 'Eco mode', 'Temp/Hum', 'Heating Temp', 'Protect'

As the away status is independent of the devices (and is in fact a combination of all the devices), the name is automatically created as *name_of_the_hardware* - *Away*.

For each created device a remark is added to the description, like '**Do not remove**: [Family Room Heating]'. The part in square brackets (inclusive) is needed to make this plugin work. It allows you changing the name of devices (but do not change the tag in the description).

## Migration
Check the description of the "Away"-device by Switches - Edit.

If the description still contains the location, remove the location part. As an example, '**Do not remove**: [Family Room Away]' should be modified to '**Do not remove**: [Away]'. 

Alternatively (if not done), a new "Away'-device will be created automatically (and you can remove the old one).

Success!

**Don't forget a small gift by using the donation button...**
