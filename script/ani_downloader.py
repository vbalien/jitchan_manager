#!/usr/bin/env python3
import http.client
import json
import re
import urllib.parse
from xml.dom.minidom import parseString
from zipfile import ZipFile

import transmissionrpc


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
        for item in data:
            if item['s'] == built_ep:
                sub_maker_url = urllib.parse.urlparse('http://' + item['a'])
                referer = 'http://' + item['a']
                break
        if sub_maker_url is None:
            return None
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
                    'all': group['all'],
                    'title': group['title'],
                    'url': link
                }
        return None

    def guess_encoding(self, text):
        guess_list = ['euc-kr', 'utf-8', 'utf-16']
        for best_enc in guess_list:
            try:
                str(text, best_enc, "strict")
            except UnicodeDecodeError:
                pass
            else:
                break
        return best_enc

    def download(self):
        sub_i = 3545
        query = 'Gyakuten Saiban'
        latest_ep = 2

        torrent = self.getTorrentUrl(query, latest_ep)
        if torrent is not None:
            tc = transmissionrpc.Client(
                self.app.config['TRANSMISSION_HOST'],
                port=self.app.config['TRANSMISSION_PORT'],
                user=self.app.config['TRANSMISSION_USER'],
                password=self.app.config['TRANSMISSION_PASSWORD']
            )
            tc.add_uri(torrent['url'])

            latest_ep += 1
            suburl = self.getSubURL(sub_i, latest_ep)
            headers = {'Referer': suburl['referer'], 'User-Agent': 'curl/7.43.0'}
            print(suburl['type'])
            global smi_data
            smi_data = None
            if suburl['type'] == 'smi':
                sub_url = urllib.parse.urlparse(suburl['url'])
                conn = http.client.HTTPConnection(sub_url.netloc)
                conn.request('GET', sub_url.path + '?' + sub_url.query, None, headers)
                res = conn.getresponse()
                smi_data = res.read()
            elif suburl['type'] == 'zip':
                sub_url = urllib.parse.urlparse(suburl['url'])
                conn = http.client.HTTPConnection(sub_url.netloc)
                conn.request('GET', sub_url.path + '?' + sub_url.query, None, headers)
                res = conn.getresponse()
                data = res.read()
                with open('tmp.zip', 'wb') as fp:
                    fp.write(data)
                with ZipFile('tmp.zip') as myzip:
                    name_best = None
                    name = None
                    for item in myzip.namelist():
                        if item.find('.smi') != -1:
                            name = item
                        m = re.match(r'.*(ohy|leo).*.smi', item)
                        if m:
                            name_best = item
                    if name_best is None:
                        name_best = name
                    with myzip.open(name_best) as myfile:
                        smi_data = myfile.read()

            charset = self.guess_encoding(smi_data)
            smi_data = smi_data.decode(charset)
            reiter = re.finditer(
                r"<SYNC Start=(?P<time>\d*)[^>]*><P Class=(?P<lang>\w*)[^>]*>(?P<text>.*&nbsp;|.*\n.*[^<SYNC]*)",
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
                    text = re.sub("<br>|<br\/>", "", text, flags=re.I)
                    out_data += self.samiTime2vttTime(beginTime) + " --> " + self.samiTime2vttTime(endTime) + "\n"
                    out_data += text + "\n\n"

            with open("{0}.vtt".format(torrent['all']), 'wb') as fp:
                fp.write(out_data.encode('utf-8'))