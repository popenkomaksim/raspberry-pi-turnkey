#!/bin/bash

sleep 3

# enable the AP
sudo cp config/hostapd /etc/default/hostapd
sudo cp config/dhcpcd.conf /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

sudo systemctl enable hostapd
sudo systemctl start hostapd

sudo reboot now
