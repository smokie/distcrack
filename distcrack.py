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

from flask import Flask, jsonify, request, send_from_directory, render_template, redirect, flash
from pymongo import MongoClient
import datetime
import os.path
from bson.json_util import dumps, default
import hashlib
from bson.objectid import ObjectId
import logger

server_host = '192.168.0.12'
server_port = 5000

logger.info("starting ...")

app = Flask(__name__)

db_conn = MongoClient(connect=False)
db = db_conn.distcrack

cap_statuses = {
    "progress": 0,
    "found": 1,
    "notfound": 2
}

pattern_map = {
    '?d': 10,
    '?l': 23,
    '?u': 23,
    '?a': 93
}


def current_path():
    return os.path.dirname(os.path.realpath(__file__))


app.config['UPLOAD_FOLDER'] = current_path() + "/uploads"
app.config['PUBLIC_FOLDER'] = current_path() + "/public"
app.config['TEMPLATES_AUTO_RELOAD'] = True


def max_comb(pattern):
    global pattern_map
    total = 1
    for k in pattern_map:
        c = pattern.count(k)
        if c > 0:
            total = total * pow(pattern_map[k], c)
    return total


@app.route('/', methods=["GET"])
def homepage():
    return redirect("/console/caps")


@app.route('/ping', methods=["GET"])
def ping():
    db.hosts.find_one_and_update({"ip": request.remote_addr}, {'$set': {"last_ping": datetime.datetime.now()}})
    return jsonify(ok=1)


@app.route('/reg', methods=["POST"])
def add_host():
    global db
    if db.hosts.count({"ip": request.remote_addr}):
        return jsonify(ok=1)
    db.hosts.insert({
        "ip": request.remote_addr,
        "os": request.form['os'],
        "user": request.form['user'],
        "hostname": request.form['hostname'],
        "created": datetime.datetime.now(),
        'last_ping': datetime.datetime.now()
    })
    return jsonify(ok=1)


def notifications():
    global db
    ret = db.notifications.find({'read': False})
    # db.notifications.delete({'read': False})
    return ret


@app.route('/caps/add', methods=["POST"])
def add_cap():
    global db, cap_statuses

    if 'cap' not in request.files:
        return jsonify(ok=0, error="missing hccapx file")

    cap = request.files['cap']
    dstpath = os.path.join(app.config['UPLOAD_FOLDER'], cap.filename)
    cap.save(dstpath)

    cap_h = open(dstpath, "br")
    cap_content = cap_h.read()

    checksum = hashlib.md5(cap_content).hexdigest()

    if db.caps.count({"checksum": checksum}) > 0:
        flash(u'Cap already exists!', "error")
        return redirect("/console/caps")

    essid = "".join(list(filter(lambda q: q != '\x00', [format(x, 'c') for x in cap_content[0xA:0xA + 0x20]])))
    bssid = "".join([format(x, 'x') for x in cap_content][0x3b:0x3b + 0x6])

    patterns = [p['source'] for p in db.patterns.find({'type': 'pattern'})]

    db.caps.insert({
        "checksum": checksum,
        "bssid": bssid,
        "essid": essid,
        "patterns": patterns,
        "status": cap_statuses['progress'],
        "cap": cap.filename
    })

    if request.is_xhr:
        return jsonify(ok=1)

    flash(u'Cap imported successfully!', "success")

    return redirect("/console/caps")


@app.route('/update', methods=["POST"])
def update():
    global db, cap_statuses

    cap = request.form['cap'],
    offset = request.form['offset'],
    status = request.form['status'],
    cap = cap[0]
    status = status[0]
    offset = offset[0]
    job = db.jobs.find_one_and_update({'cap': cap, 'offset': int(offset)}, {
        '$set': {
            'status': status
        }
    }, upsert=False)

    if status == "found":
        (jp) = request.form['jackpot']
        cap = db.caps.find_one_and_update({'bssid': job['bssid']}, {
            '$set': {
                'status': cap_statuses['found'], 'jackpot': jp
            }
        }, upsert=False)
        db.notifications.insert({
            'created': datetime.datetime.now(),
            'message': 'Password found for ' + cap['bssid'],
            'read': False
        })
        db.jobs.remove({'bssid': job['bssid']})
    else:
        if job['offset'] == job['max']:
            db.notifications.insert({
                'created': datetime.datetime.now(),
                'message': 'Password not found for ' + cap['bssid'],
                'read': False
            })

    return jsonify(ok=1)


@app.route('/fetch', methods=["GET"])
def fetch():
    global db, cap_statuses
    j = False
    cap = db.caps.find_one({"status": cap_statuses['progress']})
    if not cap:
        return jsonify(ok=1, result=[])

    jobs = db.jobs.aggregate([
        {'$match': {
            'bssid': cap['bssid']
        }
        },
        {'$group': {
            '_id': "$pattern",
            'max_offset': {'$max': '$offset'},
            'max': {'$last': '$max'}
        }
        },
        {'$project': {
            'max_offset': 1,
            'offset': 1,
            'max': 1,
            'cap': 1,
        }
        }
    ])
    for j in jobs:
        break

    if j:

        if int(j['max']) < int(j['max_offset']) + 10000:
            return ""

        pattern = j['_id']
        offset = j['max_offset'] + 10000
        maximum = j['max']
    else:
        offset = 0
        pattern = cap['patterns'][0]
        maximum = max_comb(pattern)

    ret = {
        'bssid': cap['bssid'],
        'essid': cap['essid'],
        'offset': offset,
        'max': maximum,
        'pattern': pattern,
        'cap': cap['cap'],
        'status': 'progress'
    }
    ret2 = ret.copy()
    db.jobs.insert(ret)
    return jsonify(ok=1, job=ret2, essid=cap['essid'])


@app.route('/console/clients', methods=["GET", "POST"])
def console_hosts():
    if request.is_xhr:
        if request.method == "GET":
            cursor = db.hosts.find()
            data = []

            for row in cursor:
                del row['_id']
                row['created'] = row['created'].strftime("%Y-%m-%d %H:%M:%S")
                row['last_ping'] = row['last_ping'].strftime("%Y-%m-%d %H:%M:%S")
                data.append(row)

            return jsonify(ok=1, data=data)
        if request.method == "POST":
            rec = db.hosts.insert(request.form)
            if rec.inserted_id:
                return jsonify(ok=1, data=dumps(rec, default=default))
            return jsonify(ok=0)

    return render_template("hosts.html", title="Clients", notifications=notifications())


@app.route('/console/patterns/get', methods=["GET", "POST"])
def ajax_patterns():
    if request.method == "GET":
        cursor = db.patterns.find()
        data = []
        for row in cursor:
            row['_id'] = str(row['_id'])
            if row['type'] == 'wordlist':
                row['source'] = '<a href="/uploads/wordlists/' + row['source'] + '">' + \
                                row['source'] + '</b>'
            data.append(row)
        return jsonify(ok=1, data=data)


@app.route('/console/patterns', methods=["GET", "POST"])
def console_patterns():
    if request.method == "POST":
        if 'wordlist' in request.files:
            ttype = 'wordlist'
            wordlist = request.files['wordlist']
            dstpath = os.path.join(app.config['UPLOAD_FOLDER'] + "/wordlists/", wordlist.filename)
            wordlist.save(dstpath)
            source = wordlist.filename
        else:
            ttype = 'pattern'
            source = request.form['pattern']
        if db.patterns.insert({
            "source": source,
            "type": ttype
        }):
            flash(u'Pattern added')
        else:
            flash(u'Error adding pattern', 'error')
        return redirect('/console/patterns')

    return render_template("patterns.html", title="Patterns", notifications=notifications())


@app.route('/console/hosts/<id>', methods=["DELETE", "GET", "UPDATE"])
def console_host(id):
    if request.is_xhr and request.method == "POST":
        result = db.hosts.update({'_id': id}, request.form)
        if result.modified_count:
            return jsonify(ok=1)
        return jsonify(ok=0)
    render_template("host.html", id=id, title="Host", notifications=notifications())


@app.route('/console/jobs', methods=["GET"])
def console_jobs():
    if request.is_xhr:

        data = list(db.jobs.aggregate([
            {
                '$group': {
                    '_id': {
                        'cap': '$cap'
                    },
                    'max_offset': {'$max': '$offset'},
                    'max': {'$first': '$max'},
                }
            }
        ]))
        ret = []
        _rec = {}
        print(_rec)
        for rec in data:
            _rec['cap'] = rec['_id']['cap']
            _rec['max_offset'] = rec['max_offset']
            _rec['max'] = rec['max']
            ret.append(_rec)
        return jsonify(ok=1, data=dumps(ret, default=default))

    return render_template("layout.html", title="Jobs", notifications=notifications())


@app.route('/console/caps/delete/<id>', methods=["GET"])
def del_cap(id):
    cap = db.caps.delete_many({"_id": ObjectId(id)})
    if cap:
        flash("cap deleted")
    return redirect("/console/caps")


@app.route('/console/patterns/delete/<id>', methods=["GET"])
def del_pattern(id):
    cap = db.patterns.delete_many({"_id": ObjectId(id)})
    if cap:
        flash("Pattern deleted")
    return redirect("/console/patterns")


@app.route('/console/caps', methods=["GET"])
def console_caps():
    if request.is_xhr:
        cursor = db.caps.find()
        data = []
        for row in cursor:

            cur_job = db.jobs.find_one(
                filter={'cap': row['cap']},
                projection={'offset': 1, 'max': 1},
                sort=[('$natural', -1)],
                limit=1
            )
            row['status'] = "0 %"
            if cur_job:
                row['status'] = format(cur_job['offset'] / cur_job['max'] * 100, ".2f") + " %"

            del row['patterns']
            del row['checksum']
            row['_id'] = str(row['_id'])
            data.append(row)
        return jsonify(ok=1, data=data)

    return render_template("caps.html", title="Caps", notifications=notifications())


@app.route('/js/<path:path>')
def send_js(path):
    logger.info("sending js. path: " + path)
    return send_from_directory(app.config['PUBLIC_FOLDER'] + '/js', path)


@app.route('/css/<path:path>')
def send_css(path):
    logger.info("sending css. path: " + path)
    return send_from_directory(app.config['PUBLIC_FOLDER'] + '/css', path)


@app.route('/images/<path:path>')
def send_image(path):
    logger.info("sending image. path: " + path)
    return send_from_directory(app.config['PUBLIC_FOLDER'] + '/images', path)


@app.route('/fonts/<path:path>')
def send_font(path):
    logger.info("sending image. path: " + path)
    return send_from_directory(app.config['PUBLIC_FOLDER'] + '/fonts', path)


@app.route('/uploads/wordlists/<path:path>')
def send_wl(path):
    logger.info("sending wordlist. path: " + path)
    return send_from_directory(app.config['UPLOAD_FOLDER'] + '/wordlists', path)


@app.route('/uploads/caps/<path:path>')
def send_cap(path):
    logger.info("sending cap. path: " + path)
    return send_from_directory(app.config['UPLOAD_FOLDER'] + '/caps', path)


@app.route('/uploads/hashcat/<path:path>')
def send_hashcat(path):
    logger.info("sending hashcat. path: " + path)
    return send_from_directory(app.config['UPLOAD_FOLDER'] + '/hashcat', path)


app.secret_key = b'\xe9\xed\\\xf5\xcd\x8e\x8b\x94\xf0\xce9J\xa0\xc8\xa0\x1b\xe6\xa8\xab\x1d\x16\xe9\xaf\xad'

if __name__ == '__main__':
    app.run(host=server_host, port=server_port)
