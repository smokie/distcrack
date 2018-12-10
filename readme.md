# Distcrack

Distrack is a distributed, web based solution for cracking Wifi WPA/WEP passwords written in python3. 

## Features
  - Server: Track progress, view online and offline clients, 
  manage caps and rules in a Web UI.
  - Client: windows/MacOS/Linux

## Server Requirements

- Python3
- [MongoDB](https://www.mongodb.com/)

## Installing / Running Distcrack Server

- Start MongoDB

- Install pip

```sh
# MacOS
$ easy_install pip 
# Ubuntu
$ apt install python3-pip
# CentOS
$ yum -y install python-pip
```

- Install modules
```
$ pip3 install flask
$ pip3 install requests
$ pip3 install jsonify
$ pip3 install pymongo
```

- Start distrack

```bash
$ python3 distcrackpy
```

by default, distcrack listens on *127.0.0.1* port *5000*, change the `server_host` and `server_port` variables in distrack.py if needed.

- Browse to http://[server_ip]:[server_port]

## wusgi

## Client

- Install pip

- Install modules
```
$ pip3 install requests
$ pip3 install psutil
```

- Run
```bash
$ python3 client.py
```

The client application also checks for hashcat binaries 
in case they are no found, it will attempt to download / compile Hashcat automatically


### Todos

 - Support more creacking methods
 - Gather GPU information from clients
 - Pass and use server host/port from argv
 - Pass and use client hashcat path from argv

License
----




**Free Software, Hell Yeah!**
