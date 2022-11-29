#!/usr/bin/python

import hashlib
import ssl
import json
import time
import pickle
import struct
from xml.etree.ElementTree import parse
from urllib.parse import urlencode
from urllib.request import urlopen
from contextlib import closing
import sys
import socket
from json.decoder import JSONDecodeError
import yaml
import re
import collections.abc
    
class Collector(object):

    def __init__(self, config):
        self.config = config
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.reconnect()
        
    def reconnect(self):
        self.sid = self.get_sid(self.config["fritzbox"]["user"],
                                self.config["fritzbox"]["password"])

    # See also https://github.com/shred/fritzswitch/blob/master/fritzswitch.py
    def get_sid(self, user, password):
        """Authenticate and get a Session ID"""
        with closing(urlopen("http://" + self.config["fritzbox"]["ip"] 
                             + '/login_sid.lua', None, 5)) as f:
            dom = parse(f)
            sid = dom.findtext('./SID')
            challenge = dom.findtext('./Challenge')
            
        if sid == '0000000000000000':
            md5 = hashlib.md5()
            md5.update(challenge.encode('utf-16le'))
            md5.update('-'.encode('utf-16le'))
            md5.update(password.encode('utf-16le'))
            response = challenge + '-' + md5.hexdigest()
            uri = "https://" + self.config["fritzbox"]["ip"] \
                + '/login_sid.lua?username=' \
                + user + '&response=' + response
            with closing(urlopen(uri, None, 5, context=self.ctx)) as f:
                dom = parse(f)
                sid = dom.findtext('./SID')

        if sid == '0000000000000000':
            raise PermissionError('access denied')

        return sid
    
    def get_docsis_data(self):
        uri = "https://" + self.config["fritzbox"]["ip"] + '/data.lua'
        data = urlencode(
            {"xhr" : 1, "sid": self.sid, "lang": "de",
             "page": "docInfo", "xhrId": "all", "no_sidrenew": ""})
        data = data.encode('ascii')
        with closing(urlopen(uri, data, 5, context=self.ctx)) as f:
            if f.status != 200:
                raise IOError
            try:
                data = json.load(f);
                return data["data"]
            except JSONDecodeError:
                raise IOError
                
 
    def write_obj(self, out, path, obj):
        if type(obj) is dict:
            self.write_dict(out, path, obj)
        elif type(obj) is list:
            self.write_list(out, path, obj)
        else:
            out.append((path, (str(self.timestamp), str(obj))))
    
    def write_dict(self, out, path, obj):
        for key, value in obj.items():
            if key == "multiplex" or key == "type":
                continue
            if isinstance(value, str):
                m = re.search("([0-9]+) - ([0-9]+)", value)
                if m != None:
                    self.write_obj(out, path + "." + key + "range.min", m.group(1))
                    self.write_obj(out, path + "." + key + "range.max", m.group(2))
                    continue
            self.write_obj(out, path + "." + key, value)
    
    def write_list(self, out, path, obj):
        for i in range(len(obj)):
            self.write_obj(out, path + "." + str(i), obj[i])
    
    def send_data(self, data):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as upconn:
            upconn.connect((self.config["graphite"]["server"], 
                            self.config["graphite"]["port"]))
            for metric in data:
                upconn.send((metric[0] + " " + metric[1][1] + " " + metric[1][0] + "\n").encode())

def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d
    
if __name__ == '__main__':

    config = { 
        "fritzbox": { "ip": "192.168.178.1",
                      "user": "graphite",
                      "password": "none" },

        "graphite": { "server": "localhost",
                      "port": 2003 },
        "interval": 5
        }
    
    with closing(open(sys.argv[1], "r")) as f:
        try:
            update(config, yaml.safe_load(f))
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)

    obj = Collector(config);
    while True:
        try:
            data = obj.get_docsis_data()
            obj.timestamp = int(time.time())
            prefix = "docsis." + config["fritzbox"]["ip"].replace(".", "_")
            out = []
            obj.write_dict(out, prefix + ".channelDs", data["channelDs"])
            obj.write_dict(out, prefix + ".channelUs", data["channelUs"])
            obj.send_data(out)
        except IOError:
            sys.stderr.write("Reconnecting...\n")
            obj.reconnect()
        time.sleep(int(config["interval"]))

