# -*- coding: utf-8 -*-
# Copyright (C) 2019, smokiee <smokiee@gmail.com>
# vim: set ts=4 sts=4 sw=4 expandtab smartindent:
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#  THE SOFTWARE.

import os
import os.path
import sys
import json
import re
from subprocess import Popen, PIPE, call
import time
import socket
import requests
import psutil
import zipfile
import logger

url = "http://192.168.0.12:5000"


def hashcat_path():
    os_path = [
        ('Darwin', '/usr/local/bin/hashcat'),
        ('nt', 'hashcat64.exe'),
    ]
    for (sysname, path) in os_path:
        if get_system() == sysname:
            return path
    return False


def hashcat_get():
    dir_default = '/tmp/hashcat'

    if get_system() == 'Darwin':
        call((os.getcwd() + '/get_hashcat_mac.sh', dir_default), shell=False, stdout=PIPE)
        return True
    if get_system() == 'nt':
        try:
            hashcatzip = requests.get(url + '/uploads/hashcat/hashcat.zip')
        except requests.exceptions.ConnectionError as e:
            print(e)
            return False

        with open('hashcat.zip', 'wb') as caph:
            caph.write(hashcatzip.content)
            caph.close()
            os.mkdir("hashcat")
            with zipfile.ZipFile("hashcat.zip", "r") as zip_ref:
                zip_ref.extractall(os.getcwd())
            return True
    return False


def process_exists():
    c = 0
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(['pid', 'name', 'cmdline'])
        except psutil.NoSuchProcess:
            pass
        else:
            if pinfo['cmdline'] is not None and any("client.py" in x for x in pinfo['cmdline']):
                c = c + 1

    return c > 1


def register():
    try:
        requests.post(url=url + "/reg", data={
            'os': get_system(),
            'user': os.getlogin(),
            'hostname': socket.gethostname()
        })
    except requests.exceptions.RequestException as e:
        print(e)
        return False

    return True


def ping(error=''):
    try:
        requests.get(url=url + '/ping?error=' + error, params={
            'hostname': socket.gethostname()
        })
    except requests.exceptions.RequestException as e:
        print(e)
        return False


def hashcat(offset, pattern, cap):
    cmd = [
        hashcat_path(),
        '-m 2500',
        '-a 3',
        '-s ' + str(offset),
        '-l 100',
        '"' + cap + '"',
        '"' + pattern + '"'
    ]
    logger.info('offset: ' + str(offset))
    res = Popen(' '.join(cmd), shell=True, stdout=PIPE)
    res.wait()
    if res.returncode == 0:
        for line in res.stdout:
            if re.match('Recovered.*:\s*1\/1 hashes', line.decode('ascii')) is not None:
                return True

    return False


def fetch():
    try:
        res = requests.get(url=url + '/fetch')
        json_o = json.loads(res.text)
        if 'job' in json_o:
            capname = json_o['essid'] + ".hccapx"
            ret = {}
            if os.path.isfile(capname) is False:
                logger.info("downloading cap")
                capcontent = requests.get(url + '/uploads/caps/' + capname)
                with open(capname, 'wb') as caph:
                    caph.write(capcontent.content)
                caph.close()
                logger.info("cap saved to " + capname)
            if hashcat(json_o['job']['offset'], json_o['job']['pattern'], capname):
                with open('hashcat.pot', 'r') as jh:
                    ret['jackpot'] = jh.readlines()
                jh.close()
                ret['status'] = 'found'
            else:
                ret['status'] = 'notfound'

                requests.post(url=url + '/update', data={**{
                    'cap': json_o['job']['cap'],
                    'status': 'found',
                    'offset': str(json_o['job']['offset'])
                }, **ret})

    except requests.exceptions.RequestException as e:
        print(e)
        return False
    return True


def get_system():
    if os.name == 'nt':
        return os.name
    return os.uname().sysname


if __name__ == '__main__':

    hcpath = hashcat_path()
    if os.path.isfile(hashcat_path()) is False:
        logger.warning("Hashcat not found, downloading")
        if hashcat_get() is False:
            logger.error("Error downloading hashcat, quitting...")
            sys.exit(1)
        else:
            logger.success("hashcat downloaded")
    if hashcat_path() is False:
        logger.error("hashcat executable not found in PATH")
        sys.exit(1)

        logger.info("hashcat found!")

    if register() is False:
        logger.error('error contacting distcrack server at ' + url)
        sys.exit(1)
    logger.info("starting work")
    while True:
        ping()
        fetch()
        time.sleep(5)
