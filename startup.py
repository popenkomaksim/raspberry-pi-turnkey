import subprocess
import shutil
import signal
import string
import random
import re
import json
import time
import os
from wpasupplicantconf import WpaSupplicantConf

WPA_SUPPLICANT_CONF_PATH = '/etc/wpa_supplicant/wpa_supplicant.conf'
WPA_SUPPLIANT_CONF_BACKUP_PATH = '/etc/wpa_supplicant/wpa_supplicant.bak'

from flask import Flask, request, send_from_directory, render_template, redirect
app = Flask(__name__, static_url_path='')

currentdir = os.path.dirname(os.path.abspath(__file__))
os.chdir(currentdir)

ssid_list = []
def getssid():
    global ssid_list
    if len(ssid_list) > 0:
        return ssid_list
    ssid_list = []
    get_ssid_list = subprocess.check_output(('iw', 'dev', 'wlan0', 'scan', 'ap-force'))
    ssids = get_ssid_list.splitlines()
    for s in ssids:
        s = s.strip().decode('utf-8')
        if s.startswith("SSID"):
            a = s.split(": ")
            try:
                ssid_list.append(a[1])
            except:
                pass
    print(ssid_list)
    ssid_list = sorted(list(set(ssid_list)))
    return ssid_list

def id_generator(size=6, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

@app.route('/')
def main():
    return render_template('index.html', ssids=getssid())

# Captive portal when connected with iOS or Android
@app.route('/generate_204')
def redirect204():
    return redirect("http://192.168.4.1", code=302)

@app.route('/hotspot-detect.html')
def applecaptive():
    return redirect("http://192.168.4.1", code=302)

# Not working for Windows, needs work!
@app.route('/ncsi.txt')
def windowscaptive():
    return redirect("http://192.168.4.1", code=302)

def check_cred(ssid, password):
    '''Validates ssid and password and returns True if valid and False if not valid'''
    wpadir = currentdir + '/wpa/'
    testconf = wpadir + 'test.conf'
    wpalog = wpadir + 'wpa.log'
    wpapid = wpadir + 'wpa.pid'

    if not os.path.exists(wpadir):
        os.mkdir(wpadir)

    for _file in [testconf, wpalog, wpapid]:
        if os.path.exists(_file):
            os.remove(_file)

    # Generate temp wpa.conf
    result = subprocess.check_output(['wpa_passphrase', ssid, password])
    with open(testconf, 'w') as f:
        f.write(result.decode('utf-8'))

    def stop_ap(stop):
        if stop:
            # Services need to be stopped to free up wlan0 interface
            print(subprocess.check_output(['systemctl', "stop", "hostapd", "dnsmasq", "dhcpcd"]))
        else:
            print(subprocess.check_output(['systemctl', "restart", "dnsmasq", "dhcpcd"]))
            time.sleep(15)
            print(subprocess.check_output(['systemctl', "restart", "hostapd"]))

    # Sentences to check for
    fail = "pre-shared key may be incorrect"
    success = "CTRL-EVENT-CONNECTED"

    stop_ap(True)

    result = subprocess.check_output(['wpa_supplicant',
                                      "-Dnl80211",
                                      "-iwlan0",
                                      "-c/" + testconf,
                                      "-f", wpalog,
                                      "-B",
                                      "-P", wpapid])

    checkwpa = True
    while checkwpa:
        with open(wpalog, 'r') as f:
            content = f.read()
            if success in content:
                valid_psk = True
                checkwpa = False
            elif fail in content:
                valid_psk = False
                checkwpa = False
            else:
                continue

    # Kill wpa_supplicant to stop it from setting up dhcp, dns
    with open(wpapid, 'r') as p:
        pid = p.read()
        pid = int(pid.strip())
        os.kill(pid, signal.SIGTERM)

    stop_ap(False) # Restart services
    return valid_psk

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/signin', methods=['POST'])
def signin():
    ssid = request.form['ssid']
    password = request.form['password']

    print(ssid, password)
    valid_psk = check_cred(ssid, password)
    if not valid_psk:
        # User will not see this because they will be disconnected but we need to break here anyway
        return render_template('ap.html', message="Wrong password!")

    restoreFromBackupAndUpdateNetwork(ssid, password)

    with open('status.json', 'w') as f:
        f.write(json.dumps({'status':'disconnected'}))
    print("Disabling access point")
    fullPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'disable_ap.sh')
    try:
        print(subprocess.check_output(fullPath, shell=True, stderr=subprocess.STDOUT, cwd=os.path.dirname(os.path.realpath(__file__))))
    except subprocess.CalledProcessError as callEx:
        print("Error disabling access point: " + callEx.output.decode("utf-8"))
    return render_template('index.html', message="Please wait 2 minutes to connect.")

def wificonnected():
    time.sleep(10)
    result = subprocess.check_output(['iwconfig', 'wlan0'])
    matches = re.findall(r'\"(.+?)\"', result.split(b'\n')[0].decode('utf-8'))
    if len(matches) > 0:
        print("got connected to " + matches[0])
        return True
    return False

def restoreFromBackupAndUpdateNetwork(ssid, pwd):
    if os.path.exists(WPA_SUPPLIANT_CONF_BACKUP_PATH):
        shutil.copy2(WPA_SUPPLIANT_CONF_BACKUP_PATH, WPA_SUPPLICANT_CONF_PATH)
    
    lines = []
    with open(WPA_SUPPLICANT_CONF_PATH, 'r') as supplicantFile:
        lines = supplicantFile.readlines()
    supplicantReader = WpaSupplicantConf(lines)
    if (ssid in supplicantReader.networks()):
        supplicantReader.remove_network(ssid)
    if pwd == "":
        supplicantReader.add_network(ssid, key_mgmt="NONE")
    else:
        supplicantReader.add_network(ssid, psk="\"{}\"".format(pwd))
    with open (WPA_SUPPLICANT_CONF_PATH, 'w') as supplicantFile:
        supplicantReader.write(supplicantFile)

def backupAndEmptySupplicantConf():
    shutil.copy2(WPA_SUPPLICANT_CONF_PATH, WPA_SUPPLIANT_CONF_BACKUP_PATH)
    lines = []
    with open(WPA_SUPPLICANT_CONF_PATH, 'r') as supplicantFile:
        lines = supplicantFile.readlines()
    supplicantReader = WpaSupplicantConf(lines)

    for network in list(supplicantReader.networks().keys()):
        supplicantReader.remove_network(network)
    with open (WPA_SUPPLICANT_CONF_PATH, 'w') as supplicantFile:
        supplicantReader.write(supplicantFile)

if __name__ == "__main__":
    # get status
    s = {'status':'disconnected'}
    if not os.path.isfile('status.json'):
        with open('status.json', 'w') as f:
            f.write(json.dumps(s))
    else:
        s = json.load(open('status.json'))

    # check connection
    if wificonnected():
        s['status'] = 'connected'
    else:
        if s['status'] == 'connected': # Don't change if status in status.json is hostapd
            s['status'] = 'disconnected'

    with open('status.json', 'w') as f:
        f.write(json.dumps(s))
    if s['status'] == 'disconnected':
        s['status'] = 'hostapd'
        with open('status.json', 'w') as f:
            f.write(json.dumps(s))
        
        print("Enabling access point")
        backupAndEmptySupplicantConf()
        fullPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'enable_ap.sh')
        try:
            print(subprocess.check_output(fullPath, shell=True, stderr=subprocess.STDOUT, cwd=os.path.dirname(os.path.realpath(__file__))))
        except subprocess.CalledProcessError as callEx:
            print("Error enabling access point: " + callEx.output.decode("utf-8"))

    elif s['status'] == 'connected':
        print("Connected to WiFi - no access point needed")
        pass
    else:
        print("Running turnkey portal")
        app.run(host="0.0.0.0", port=80, threaded=True)
