# Raspberry Pi Turnkey

Have you ever wanted to setup a Raspberry Pi *without having to SSH or attach a keyboard* to add your WiFi credentials? This is particularly useful when you are making a Raspberry Pi that needs to be deployed somewhere where supplying the credentials via SSH or attaching a keyboard isn't an option. Or it could be useful if you take your Pi to a friend's house and they don't have ethernet cables or extra keyboards+monitors to put your friend's WiFi credentials onto the Pi. With this image base you don't ever need to modify a `wpa_supplicant` with SSH/terminal/PiBakery again!

You can [follow the instructions below](#instructions-to-create-image) to create a turnkey image, or you can just download my latest one at [raspberry-pi-turnkey.schollz.com/2018-06-25-turnkey-1.3.zip](https://raspberry-pi-turnkey.schollz.com/2018-06-25-turnkey-1.3.img.zip) ([v1.3.0](https://github.com/schollz/raspberry-pi-turnkey/releases/tag/v1.3.0), 982MB) and [follow the typical flashing instructions](https://www.raspberrypi.org/documentation/installation/installing-images/README.md). 

[![Support](https://img.shields.io/badge/donate-$5-brown.svg)](https://www.paypal.me/ZackScholl/5.00)

# Usage 

Once you boot the Pi with this image, wait about 10 minutes for the Pi to reformat the drive and start up the web server. Then you will see a WiFi AP named "ConnectToConnect" (password same). Connect to it and your browser should automatically redirect you to a sign-in page. If not, navigate to `192.168.4.1` where you'll see a login form. 

<p align="center">
  <img src="https://user-images.githubusercontent.com/6550035/36927004-9dd66774-1e2f-11e8-941a-aa192005b2d6.png"/>
</p>

When the WiFi credentials are entered onto the login form, the Pi will modify its internal `wpa_supplicant` to conform to them so that it will be connected to the net. The Pi will then reboot itself using those WiFi credentials. If the credentials are not correct, then the Pi will reboot back into the AP mode to allow you to re-enter them again.

Once connected, you can recieve a message with the LAN IP for your Pi at https://snaptext.live (the specific URL will be given to you when you enter in the credentials to the form).

_Note:_ The Raspberry Pi is **not** a fast computer. When you see the AP and connect to it, it may take up to a minute for the page at `192.168.4.1` to appear. Also, if you enter the wrong WiFi credentials, it will have to reboot twice to reset the Pi to allow you to enter the credentials again. So try to enter them right the first time!

# How does it work?

When the Pi starts up it runs a Python script, `startup.py`. This script first checks if the Pi is online (by looking for an SSID in `iwconfig wlan0`). If the Pi is online, the script sets the status as "connected" (saved to disk in `status.json`).

If the Pi is not online, it will check the status. The initial status is "disconnected". When "disconnected" the Pi will uncomment the configuration files for `hostapd` and `dnsmasq`. The access point configuration is nearly identical [to as outlined in this tutorial](https://www.raspberrypi.org/documentation/configuration/wireless/access-point.md). Then the Pi sets the status as "hostapd" and reboots itself.

When the status is "hostapd" then the script will bind to port 80 and serve a web form at `192.168.4.1`. Once you connect to the AP this web form will be available and it will recieve input. Once the server recieves input, it sets the credentials in `wpa_supplicant.conf` and comments out the configuration file for `hostapd` and `dnsmasq` so that the AP doesn't interfere, and then reboots. When it reboots it will see if it gets online and set the status as "connected" or "disconnected". Then it repeats the steps above (i.e. doing nothing if connected, or restarting the AP if disconnected).

# Instructions to create image

The following are the step-by-step instructions for how I create the turnkey image. If you don't want to download the image I created above (I don't blame you), then follow these to make one exactly the same.

These instructions assume you are using Ubuntu. You can use Windows/OS X for most of these steps, except step #4 which requires resizing.

[Getting up Pi Zero OTG - The quick way (No USB keyboard, mouse, HDMI monitor needed)](https://gist.github.com/gbaman/975e2db164b3ca2b51ae11e45e8fd40a)

## 2. Install libraries onto the Raspberry Pi

SSH into your Pi using Ethernet, as you will have to disable the WiFi connection when you install `hostapd`.

### Basic libraries

```
$ sudo apt-get update
$ sudo apt-get dist-upgrade -y
$ sudo apt-get install -y dnsmasq hostapd vim python3-flask python3-requests git pip

$ sudo -H pip install wpasupplicantconf
```

### Install turnkey

```
$ git clone https://github.com/popenkomaksim/raspberry-pi-turnkey.git

$ sudo cp ./raspberry-pi-turnkey/turnkey.service /etc/systemd/system/turnkey.service
$ systemctl start turnkey
$ systemctl enable turnkey
```

### Add `pi` to sudoers

Add `pi` to the sudoers, so that you can run sudo commands without having to be root (so that all the paths to your programs are unchanged).

```
$ sudo visudo
```

Then add this line:

```
pi      ALL=(ALL:ALL) ALL
```

(_Sidenote:_ I save an image `intermediate.img` at this point so its easy to go back)



### Install Hostapd

```
$ sudo systemctl stop dnsmasq && sudo systemctl stop hostapd

$ echo 'interface wlan0
static ip_address=192.168.4.1/24' | sudo tee --append /etc/dhcpcd.conf

$ sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig  
$ sudo systemctl daemon-reload
$ sudo systemctl restart dhcpcd

$ echo 'interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h' | sudo tee --append /etc/dnsmasq.conf

$ echo 'interface=wlan0
driver=nl80211
ssid=ConnectToConnect
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0' | sudo tee --append /etc/hostapd/hostapd.conf

$ echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee --append /etc/default/hostapd

$ sudo systemctl unmask hostapd && sudo systemctl unmask dnsmasq && sudo systemctl start hostapd && sudo systemctl start dnsmasq
```


### Shutdown the pi

Shutdown the Raspberry Pi and do not start it up until after you write the image. Otherwise the unique ID that is generated will be the same for all the images.

```
$ sudo shutdown now
```

## 3. Resize Raspberry Pi SD image


These instructions assume you are using Ubuntu. You can use Windows/OS X for most of these steps, except step #4 which requires resizing.

If you don't want to resize the image, you can just write the entire image file to your computer and use that from here on. If you do want to resize (especially useful if you are installing on a 16GB card and want to flash onto a smaller card), follow these instructions.

Put the newly made image into Ubuntu and do

```
$ xhost +local:
$ sudo gparted-pkexec
```

Right click on the SD card image and do "Unmount". Then right click on the image and do "Resize/Move" and change the size to `2400`. 

Then you can copy the image to your computer using the following command

```
$ sudo dd if=/dev/mmcblk0 of=/some/place/turnkey.img bs=1M count=2400 status=progress
```

Again `/dev/mmcblk0` is your SD card which you can determine using `fdisk -l`.  The location of the image, `/some/place/`, should be set by you.

## 4. Test the turnkey image

The new image will be in `/some/place/2018-turnkey.img` which you can use to flash other SD cards. To test it out, get a new SD card and do:

```
$ sudo dd bs=4M if=/some/place/turnkey.img of=/dev/mmcblk0 conv=fsync status=progress
```


# Thanks

Thanks to [@ilirb](https://github.com/ilirb) for checking if passphrase is correct before rebooting!

# License 

MIT
