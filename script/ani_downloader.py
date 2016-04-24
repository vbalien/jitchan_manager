#!/usr/bin/env python3
from datetime import datetime
from datetime import time
import http.client
import io
import json
import os
import re
import urllib.parse
from xml.dom.minidom import parseString
from zipfile import ZipFile

import transmissionrpc

from application.ani.model import Animation
from application.ani.model import Episode


class AniDownloader(object):
    def __init__(self, app, db):
        super(AniDownloader, self).__init__()
        self.app = app
        self.db = db

    def samiTime2vttTime(self, samiTime):
        samiTime = int(samiTime)
        sec = samiTime / 1000 % 60
        min = samiTime / 1000 / 60 % 60
        hour = samiTime / 1000 / 60 / 60
        return "{0:02d}:{1:02d}:{2:06.3f}".format(int(hour), int(min), float(sec))

    def getSubURL(self, index, ep):
        params = urllib.parse.urlencode({'i': index})
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        conn = http.client.HTTPConnection("www.anissia.net")
        conn.request('POST', '/anitime/cap', params, headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode())

        if len(data) == 0:
            return None

        built_ep = "{0:05d}".format(ep * 10)
        sub_maker_url = None
        referer = ''
        for item in data[::-1]:
            if item['s'] == built_ep:
                sub_maker_url = urllib.parse.urlparse('http://' + item['a'])
                referer = 'http://' + item['a']
            if sub_maker_url is None:
                continue
            conn = http.client.HTTPConnection(sub_maker_url.netloc)
            conn.request('GET', sub_maker_url.path+'?'+sub_maker_url.query)
            res = conn.getresponse()
            charset = 'utf-8'
            m = re.search(r"charset=(.*[^;\r\n])", res.getheader('Content-Type'))
            if m:
                charset = m.group(1)
            source = res.read().decode(charset)
            frame_pos = source.find('<frame id="mainFrame" name="mainFrame" src="')
            if frame_pos != -1:  # naver blog frame
                source = source[
                    frame_pos + len('<frame id="mainFrame" name="mainFrame" src="'):]
                nblog_url = source[:source.find('"')]
                conn = http.client.HTTPConnection('blog.naver.com')
                conn.request('GET', nblog_url)
                res = conn.getresponse()
                m = re.search(r"charset=(.*[^;\r\n])", res.getheader('Content-Type'))
                if m:
                    charset = m.group(1)
                source = res.read().decode(charset)

            m = re.search(
                r"(?P<zip>http:\/\/[^ \'\n]*\.zip)|(?P<smi>http:\/\/[^ \'\n]*\.smi)",
                source
            )
            if m:
                group = m.groupdict()
                if group['smi'] is not None:
                    return {
                        'type': 'smi',
                        'url': group['smi'],
                        'referer': referer
                    }
                else:
                    return {
                        'type': 'zip',
                        'url': group['zip'],
                        'referer': referer
                    }
        return None

    def getTorrentUrl(self, query, latest_ep):
        conn = http.client.HTTPConnection('leopard-raws.org')
        conn.request('GET', '/rss.php?search=' + urllib.parse.quote_plus(query))
        res = conn.getresponse()
        charset = 'utf-8'
        m = re.search(r"charset=(.*[^;\r\n])", res.getheader('Content-Type'))
        if m:
            charset = m.group(1)
        source = res.read().decode(charset)
        items = parseString(source).getElementsByTagName('item')
        prog = re.compile(
            r"(?P<all>\[(?P<raw>.*)\] (?P<title>.*) - (?P<ep>.\d).*)\.(?P<ext>.*)"
            )
        for item in items:
            title = item.getElementsByTagName('title')[0].firstChild.data
            m = prog.search(title)
            if m is None:
                return None
            group = m.groupdict()
            if (latest_ep + 1) == int(group['ep']):
                link = item.getElementsByTagName('link')[0].firstChild.data
                return {
                    'filename': group['all'],
                    'ext': group['ext'],
                    'title': group['title'],
                    'ep': group['ep'],
                    'url': link
                }
        return None

    def guess_encoding(self, text):
        guess_list = ['euc-kr', 'utf-8', 'utf-16', None]
        for best_enc in guess_list:
            if best_enc is None:
                return None
            try:
                str(text, best_enc, "strict")
            except UnicodeDecodeError:
                pass
            else:
                break
        return best_enc

    def download(self):
        now_datetime = datetime.now()
        min_hour = now_datetime.hour - 6
        min_time = time(hour=min_hour % 12, minute=now_datetime.minute)
        my_oper = None
        anissia_week = []
        quarter_datetimes = [
            {  # 1분기
                'start': datetime(year=now_datetime.year-1, month=12, day=1),
                'end': datetime(year=now_datetime.year, month=5, day=1)
            },
            {  # 2분기
                'start': datetime(year=now_datetime.year, month=3, day=1),
                'end': datetime(year=now_datetime.year, month=8, day=1)
            },
            {  # 3분기
                'start': datetime(year=now_datetime.year, month=6, day=1),
                'end': datetime(year=now_datetime.year, month=11, day=1)
            },
            {  # 4분기
                'start': datetime(year=now_datetime.year, month=9, day=1),
                'end': datetime(year=now_datetime.year+1, month=2, day=1)
            },
        ]
        quart_index = 0
        for index, quart_datetime in enumerate(quarter_datetimes):
            if now_datetime >= quart_datetime['start'] and now_datetime <= quart_datetime['end']:
                quart_index = index
                break

        if min_hour < 0:
            my_oper = self.db.or_(
                self.db.and_(
                    Animation.week == (now_datetime.weekday() - 1) % 7,
                    self.db.or_(
                        Animation.release_datetime.is_(None),
                        self.db.and_(
                            self.db.func.time(Animation.release_datetime) >= min_time,
                            Animation.release_datetime >= quarter_datetimes[quart_index]['start'],
                            Animation.release_datetime <= quarter_datetimes[quart_index]['end']
                        )
                    )
                ),
                self.db.and_(
                    Animation.week == now_datetime.weekday(),
                    self.db.or_(
                        Animation.release_datetime.is_(None),
                        self.db.and_(
                            self.db.func.time(Animation.release_datetime) <= datetime.now().time(),
                            Animation.release_datetime >= quarter_datetimes[quart_index]['start'],
                            Animation.release_datetime <= quarter_datetimes[quart_index]['end']
                        )
                    )
                )
            )
            params = urllib.parse.urlencode({'w': now_datetime.weekday() % 7})
            headers = {"Content-type": "application/x-www-form-urlencoded"}
            conn = http.client.HTTPConnection("www.anissia.net")
            conn.request('POST', '/anitime/list', params, headers)
            res = conn.getresponse()
            anissia_week += json.loads(res.read().decode())
        else:
            my_oper = self.db.and_(
                Animation.week == now_datetime.weekday(),
                self.db.or_(
                    Animation.release_datetime.is_(None),
                    self.db.and_(
                        self.db.func.time(Animation.release_datetime) >= min_time,
                        self.db.func.time(Animation.release_datetime) <= datetime.now().time(),
                        Animation.release_datetime >= quarter_datetimes[quart_index]['start'],
                        Animation.release_datetime <= quarter_datetimes[quart_index]['end']
                    )
                )
            )
        params = urllib.parse.urlencode({'w': (now_datetime.weekday() + 1) % 7})
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        conn = http.client.HTTPConnection("www.anissia.net")
        conn.request('POST', '/anitime/list', params, headers)
        res = conn.getresponse()
        anissia_week += json.loads(res.read().decode())

        active_anilist = self.db.session.query(Animation).filter(
            my_oper
        ).all()
        print(active_anilist)
        for ani in active_anilist:
            sub_i = ani.sync_index
            query = ani.query

            if ani.release_datetime is None:
                for item in anissia_week:
                    print(int(item['i']), ani.sync_index)
                    if int(item['i']) == ani.sync_index:
                        release_datetime = datetime(
                            year=int(item['sd'][:4]),
                            month=int(item['sd'][4:6]),
                            day=int(item['sd'][-2:]),
                            hour=int(item['t'][:2]),
                            minute=int(item['t'][2:])
                        )
                        ani.release_datetime = release_datetime
                        self.db.session.commit()
                        break

            while True:
                torrent = self.getTorrentUrl(query, ani.latest_ep_num)
                if torrent is None:
                    break
                down_dir = self.app.config['ANI_DOWNLOAD_DIR'] + '/' + torrent['title']
                sync_dir = self.app.config['ANI_SYNC_DIR'] + '/' + torrent['title']
                if not os.path.isdir(sync_dir):
                    os.makedirs(sync_dir)
                tc = transmissionrpc.Client(
                    self.app.config['TRANSMISSION_HOST'],
                    port=self.app.config['TRANSMISSION_PORT'],
                    user=self.app.config['TRANSMISSION_USER'],
                    password=self.app.config['TRANSMISSION_PASSWORD']
                )
                torrent_obj = tc.add_torrent(
                    torrent['url'],
                    download_dir=down_dir
                )
                episode = Episode()
                episode.ep_num = torrent['ep']
                episode.torrent_id = torrent_obj.id
                episode.video_path = '{0}/{1}.{2}'.format(down_dir, torrent['filename'], torrent['ext'])

                ani.latest_ep_num += 1
                self.db.session.commit()

                suburl = self.getSubURL(sub_i, ani.latest_ep_num)
                if suburl is not None:
                    headers = {'Referer': suburl['referer'], 'User-Agent': 'curl/7.43.0'}
                    global smi_data
                    smi_data = None
                    sub_url = urllib.parse.urlparse(suburl['url'])
                    while True:
                        conn = http.client.HTTPConnection(sub_url.netloc)
                        conn.request(
                            'GET',
                            sub_url.path + ((sub_url.query != '') and '?' + sub_url.query or ''),
                            None,
                            headers
                        )
                        res = conn.getresponse()
                        if res.status != 302:
                            break
                        else:
                            sub_url = urllib.parse.urlparse(res.getheader('Location'))
                    if suburl['type'] == 'smi':
                        smi_data = res.read()
                    elif suburl['type'] == 'zip':
                        zip_object = io.BytesIO(res.read())
                        with ZipFile(zip_object) as myzip:
                            name_best = None
                            name = None
                            for item in myzip.namelist():
                                if item.find('.smi') != -1:
                                    name = item
                                    m = re.match(r'.*(ohy|leo).*.smi', item, flags=re.I)
                                    if m:
                                        name_best = item
                                        break
                            if name_best is None:
                                name_best = name
                            with myzip.open(name_best) as myfile:
                                smi_data = myfile.read()

                    charset = self.guess_encoding(smi_data)
                    if charset is None:
                        continue
                    smi_data = smi_data.decode(charset)
                    reiter = re.finditer(
                        r"<SYNC Start=(?P<time>\d*)[^>]*><P Class=(?P<lang>\w*)[^>]*>(?P<text>(?:(?!<SYNC)[\s\S])*)",
                        smi_data,
                        flags=re.I
                    )
                    sync_list = []
                    out_data = "WEBVTT\n\n"
                    for item in reiter:
                        sync_list.append(item.groupdict())
                    for index, item in enumerate(sync_list):
                        beginTime = int(item['time'])
                        try:
                            endTime = int(sync_list[index+1]['time'])
                        except IndexError:
                            endTime = beginTime + 10000
                        else:
                            pass
                        text = item['text'].strip()
                        if text != '&nbsp;':
                            text = re.sub("<br>|<br\/>|</.*>", "", text, flags=re.I)
                            if text.strip() == '':
                                continue
                            out_data += self.samiTime2vttTime(beginTime) + \
                                " --> " + self.samiTime2vttTime(endTime) + "\n"
                            out_data += text + "\n\n"
                    syncname = "{0}/{1}.vtt".format(sync_dir, torrent['filename'])
                    with open(syncname, 'wb') as fp:
                        fp.write(out_data.encode('utf-8'))
                    episode.sync_path = syncname
                ani.episodes.append(episode)
                self.db.session.commit()
