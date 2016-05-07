#!/usr/bin/env python3
from datetime import date
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


def guess_encoding(text):
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


def samiTime2vttTime(samiTime):
    samiTime = int(samiTime)
    sec = samiTime / 1000 % 60
    min = samiTime / 1000 / 60 % 60
    hour = samiTime / 1000 / 60 / 60
    return "{0:02d}:{1:02d}:{2:06.3f}".format(int(hour), int(min), float(sec))


def smi2vtt(smi_data):
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
            text = re.sub("<br>|<br\/>|</.*>", "", text, flags=re.I).strip()
            if text == '':
                continue
            out_data += samiTime2vttTime(beginTime) + \
                " --> " + samiTime2vttTime(endTime) + "\n"
            out_data += text + "\n\n"
    return out_data


class AniDownloader(object):
    def __init__(self, app, db):
        super(AniDownloader, self).__init__()
        self.app = app
        self.db = db

    def getSubURL(self, index, ep, pass_num=0):
        pass_count = 0
        ep = int(ep)
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
            print('ep:', item['s'], built_ep)
            if item['s'] == built_ep:
                if pass_count == pass_num:
                    sub_maker_url = urllib.parse.urlparse('http://' + item['a'])
                    referer = 'http://' + item['a']
                else:
                    pass_count = pass_count + 1
                    continue
            else:
                continue
            print('sub_maker_url:', sub_maker_url)
            conn = http.client.HTTPConnection(sub_maker_url.netloc)
            conn.request('GET', sub_maker_url.path+'?'+sub_maker_url.query)
            res = conn.getresponse()
            charset = 'utf-8'
            m = re.search(r"charset=(.*[^;\r\n])", res.getheader('Content-Type'))
            if m:
                charset = m.group(1)
            try:
                source = res.read().decode(charset)
            except UnicodeDecodeError:
                continue
            screen_frame_pos = source.find('<frame id="screenFrame" name="screenFrame" src=\'')
            if screen_frame_pos != -1:  # naver blog frame
                source = source[
                    screen_frame_pos + len('<frame id="screenFrame" name="screenFrame" src=\''):]
                nblog_url = source[:source.find('\'')]
                nblog_url = urllib.parse.urlparse(nblog_url)
                conn = http.client.HTTPConnection('blog.naver.com')
                conn.request('GET', nblog_url.path+'?'+nblog_url.query)
                res = conn.getresponse()
                m = re.search(r"charset=(.*[^;\r\n])", res.getheader('Content-Type'))
                if m:
                    charset = m.group(1)
                source = res.read().decode(charset)

            main_frame_pos = source.find('<frame id="mainFrame" name="mainFrame" src="')
            if main_frame_pos != -1:  # naver blog frame
                source = source[
                    main_frame_pos + len('<frame id="mainFrame" name="mainFrame" src="'):]
                nblog_url = source[:source.find('"')]
                nblog_url = urllib.parse.urlparse(nblog_url)
                conn = http.client.HTTPConnection('blog.naver.com')
                conn.request('GET', nblog_url.path+'?'+nblog_url.query)
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

    def getTorrentUrl(self, query, episode):
        conn = http.client.HTTPConnection('torrents.ohys.net')
        conn.request('GET', '/rss.php?dir=torrent&q=' + urllib.parse.quote_plus(query))
        res = conn.getresponse()
        charset = 'utf-8'
        m = re.search(r"charset=(.*[^;\r\n])", res.getheader('Content-Type'))
        if m:
            charset = m.group(1)
        source = res.read().decode(charset)
        items = parseString(source).getElementsByTagName('item')
        prog = re.compile(
            r"(?P<filename>\[(?P<raw>.*)\] (?P<title>.*) - (?P<ep>.\d).*)\.(?P<ext>.*)\.torrent"
            )
        for item in items:
            title = item.getElementsByTagName('title')[0].firstChild.data
            m = prog.search(title)
            if m is None:
                continue
            group = m.groupdict()
            if (episode + 1) == int(group['ep']):
                link = item.getElementsByTagName('link')[0].firstChild.data
                return {
                    'filename': group['filename'],
                    'ext': group['ext'],
                    'title': group['title'],
                    'ep': group['ep'],
                    'url': link
                }
        return None

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
                Animation.release_datetime.is_(None),
                self.db.and_(
                    Animation.week == (now_datetime.weekday() - 1) % 7,
                    self.db.and_(
                        self.db.func.time(Animation.release_datetime) >= min_time,
                        Animation.release_datetime >= quarter_datetimes[quart_index]['start'],
                        Animation.release_datetime <= quarter_datetimes[quart_index]['end']
                    )
                ),
                self.db.and_(
                    Animation.week == now_datetime.weekday(),
                    self.db.and_(
                        self.db.func.time(Animation.release_datetime) <= datetime.now().time(),
                        Animation.release_datetime >= quarter_datetimes[quart_index]['start'],
                        Animation.release_datetime <= quarter_datetimes[quart_index]['end']
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
            my_oper = self.db.or_(
                Animation.release_datetime.is_(None),
                self.db.and_(
                    Animation.week == now_datetime.weekday(),
                    self.db.func.time(Animation.release_datetime) >= min_time,
                    self.db.func.time(Animation.release_datetime) <= datetime.now().time(),
                    Animation.release_datetime >= quarter_datetimes[quart_index]['start'],
                    Animation.release_datetime <= quarter_datetimes[quart_index]['end']
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
        for ani in active_anilist:
            print(ani)
            sync_index = ani.sync_index
            query = ani.query

            if ani.release_datetime is None or ani.end_date is None:
                for item in anissia_week:
                    if int(item['i']) == ani.sync_index:
                        if ani.release_datetime is None:
                            release_datetime = datetime(
                                year=int(item['sd'][:4]),
                                month=int(item['sd'][4:6]),
                                day=int(item['sd'][-2:]),
                                hour=int(item['t'][:2]),
                                minute=int(item['t'][2:])
                            )
                            ani.release_datetime = release_datetime

                        if ani.end_date is None and int(item['ed']) != 0:
                            end_date = date(
                                year=int(item['ed'][:4]),
                                month=int(item['ed'][4:6]),
                                day=int(item['ed'][-2:])
                            )
                            ani.end_date = end_date
                        self.db.session.commit()
                        break

            while True:
                torrent = self.getTorrentUrl(query, ani.latest_ep_num)
                if torrent is None:
                    print('none')
                    episode = [
                        item for item in ani.episodes
                        if item.ep_num == ani.latest_ep_num
                        and item.hasSync() is False
                        ]
                    if len(episode) == 0:
                        break
                    episode = episode[0]
                    # Sync
                    sync_data = self.getSyncData(sync_index, episode.ep_num)
                    if sync_data is None:
                        break
                    with open(episode.getSyncFullPath(), 'wb') as fp:
                        fp.write(sync_data.encode('utf-8'))
                    print(episode.getSyncFullPath())
                    # episode.sync_path = sync_path
                    self.db.session.commit()
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
                episode.filename = os.path.splitext(torrent_obj.name)[0]
                episode.video_ext = torrent['ext']
                # episode.video_path = '/{0}/{1}'.\
                #     format(torrent['title'], torrent_obj.name)
                ani.episodes.append(episode)
                if ani.synonyms is None:
                    ani.synonyms = torrent['title']

                ani.latest_ep_num += 1
                self.db.session.commit()

                # Sync
                sync_data = self.getSyncData(sync_index, torrent['ep'])
                if sync_data is None:
                    continue
                with open(episode.getSyncFullPath(), 'wb') as fp:
                    fp.write(sync_data.encode('utf-8'))
                self.db.session.commit()

    def getSyncData(self, sync_index, episode):
        pass_num = 0
        while True:
            suburl = self.getSubURL(sync_index, episode, pass_num)
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
                    print('sub_url:', sub_url)
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
                            if item.lower().find('.smi') != -1:
                                name = item
                                m = re.match(
                                    r'.*(ohy|leo| s\.| s |-s\.| s-).*smi$',
                                    item,
                                    flags=re.I)
                                if m:
                                    name_best = item
                                    m = re.match(
                                        r'.*[\D]{0}[\D].*smi$'.format(
                                            episode),
                                        item)
                                    if m:
                                        break
                        if name_best is None:
                            name_best = name
                        with myzip.open(name_best) as myfile:
                            smi_data = myfile.read()

                charset = guess_encoding(smi_data)
                if charset is None:
                    print("Pass this sync")
                    pass_num = pass_num + 1
                    continue
                smi_data = smi_data.decode(charset)
                return smi2vtt(smi_data)
            else:
                return None
