# coding=utf-8
# !/usr/bin/python

"""

作者 丢丢喵 🚓 内容均从互联网收集而来 仅供交流学习使用 版权归原创者所有 如侵犯了您的权益 请通知作者 将及时删除侵权内容
                    ====================Diudiumiao====================

"""

from Crypto.Util.Padding import unpad
from Crypto.Util.Padding import pad
from urllib.parse import unquote
from Crypto.Cipher import ARC4
from urllib.parse import quote
from base.spider import Spider
from Crypto.Cipher import AES
from datetime import datetime
from bs4 import BeautifulSoup
from base64 import b64decode
import urllib.request
import urllib.parse
import datetime
import binascii
import requests
import base64
import json
import time
import sys
import re
import os

sys.path.append('..')

xurl = "https://search.bilibili.com"

xurl1 = "https://api.live.bilibili.com"

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
    'Referer': 'https://live.bilibili.com/',
    'Origin': 'https://live.bilibili.com',
}

PLAY_HEADERS = {
    'User-Agent': headerx['User-Agent'],
    'Referer': 'https://live.bilibili.com/',
    'Origin': 'https://live.bilibili.com',
    'Accept': '*/*',
}

class Spider(Spider):
    global xurl
    global xurl1
    global headerx

    def getName(self):
        return "首页"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def extract_middle_text(self, text, start_str, end_str, pl, start_index1: str = '', end_index2: str = ''):
        if pl == 3:
            plx = []
            while True:
                start_index = text.find(start_str)
                if start_index == -1:
                    break
                end_index = text.find(end_str, start_index + len(start_str))
                if end_index == -1:
                    break
                middle_text = text[start_index + len(start_str):end_index]
                plx.append(middle_text)
                text = text.replace(start_str + middle_text + end_str, '')
            if len(plx) > 0:
                purl = ''
                for i in range(len(plx)):
                    matches = re.findall(start_index1, plx[i])
                    output = ""
                    for match in matches:
                        match3 = re.search(r'(?:^|[^0-9])(\d+)(?:[^0-9]|$)', match[1])
                        if match3:
                            number = match3.group(1)
                        else:
                            number = 0
                        if 'http' not in match[0]:
                            output += f"#{match[1]}${number}{xurl}{match[0]}"
                        else:
                            output += f"#{match[1]}${number}{match[0]}"
                    output = output[1:]
                    purl = purl + output + "$$$"
                purl = purl[:-3]
                return purl
            else:
                return ""
        else:
            start_index = text.find(start_str)
            if start_index == -1:
                return ""
            end_index = text.find(end_str, start_index + len(start_str))
            if end_index == -1:
                return ""

        if pl == 0:
            middle_text = text[start_index + len(start_str):end_index]
            return middle_text.replace("\\", "")

        if pl == 1:
            middle_text = text[start_index + len(start_str):end_index]
            matches = re.findall(start_index1, middle_text)
            if matches:
                jg = ' '.join(matches)
                return jg

        if pl == 2:
            middle_text = text[start_index + len(start_str):end_index]
            matches = re.findall(start_index1, middle_text)
            if matches:
                new_list = [f'{item}' for item in matches]
                jg = '$$$'.join(new_list)
                return jg

    def homeContent(self, filter):
        result = {}
        result = {"class": [{"type_id": "舞", "type_name": "舞蹈"},
                            {"type_id": "音乐", "type_name": "音乐"},
                            {"type_id": "手游", "type_name": "手游"},
                            {"type_id": "网游", "type_name": "网游"},
                            {"type_id": "单机游戏", "type_name": "单机游戏"},
                            {"type_id": "虚拟主播", "type_name": "虚拟主播"},
                            {"type_id": "电台", "type_name": "电台"},
                            {"type_id": "体育", "type_name": "体育"},
                            {"type_id": "聊天", "type_name": "聊天"},
                            {"type_id": "娱乐", "type_name": "娱乐"},
                            {"type_id": "电影", "type_name": "影视"},
                            {"type_id": "新闻", "type_name": "新闻"}]
                 }

        return result

    def homeVideoContent(self):
        pass

    def _parse_live_cards(self, html):
        doc = BeautifulSoup(html, "lxml")
        soups = doc.find_all('div', class_="video-list-item")
        if not soups:
            soups = doc.select('.bili-live-card, .live-card')
        videos = []
        for vod in soups:
            names = vod.find('h3', class_="bili-live-card__info--tit")
            if not names:
                names = vod.select_one('.bili-live-card__info--tit, .live-card-title, h3')
            if not names:
                continue
            name = names.text.strip().replace('直播中', '')
            link = names.find('a') or vod.find('a')
            if not link or not link.get('href'):
                continue
            vid = self.extract_middle_text(link['href'], 'bilibili.com/', '?', 0)
            if not vid:
                m = re.search(r'/(\d+)', link['href'])
                vid = m.group(1) if m else ''
            if not vid:
                continue
            img = vod.find('img')
            pic = img.get('src') if img else ''
            if pic and 'http' not in pic:
                pic = "https:" + pic
            remarks = vod.find('a', class_="bili-live-card__info--uname")
            remark = remarks.text.strip() if remarks else ''
            videos.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return videos

    def categoryContent(self, cid, pg, filter, ext):
        result = {}
        if pg:
            page = int(pg)
        else:
            page = 1
        url = f'{xurl}/live?keyword={cid}&page={str(page)}'
        detail = requests.get(url=url, headers=headerx, timeout=15)
        detail.encoding = "utf-8"
        videos = self._parse_live_cards(detail.text)
        result = {'list': videos}
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def _build_bili_play_lines(self, room_id):
        lines = []
        play = requests.get(
            f'{xurl1}/room/v1/Room/playUrl',
            params={'cid': room_id, 'qn': 10000, 'platform': 'web'},
            headers=PLAY_HEADERS,
            timeout=15,
        ).json()
        if play.get('code') == 0:
            play_data = play.get('data') or {}
            quality_desc = {
                item['qn']: item['desc']
                for item in play_data.get('quality_description', [])
                if isinstance(item, dict)
            }
            for qn in sorted(
                [int(q) for q in play_data.get('accept_quality', []) if str(q).isdigit()],
                reverse=True,
            ):
                qn_play = requests.get(
                    f'{xurl1}/room/v1/Room/playUrl',
                    params={'cid': room_id, 'qn': qn, 'platform': 'web'},
                    headers=PLAY_HEADERS,
                    timeout=15,
                ).json()
                if qn_play.get('code') != 0:
                    continue
                durl = (qn_play.get('data') or {}).get('durl') or []
                if not durl:
                    continue
                name = quality_desc.get(qn, f'清晰度{qn}')
                lines.append((name, durl[0].get('url') or ''))
            if lines:
                return lines

        detail = requests.get(
            f'{xurl1}/xlive/web-room/v2/index/getRoomPlayInfo',
            params={
                'room_id': room_id,
                'platform': 'web',
                'protocol': '0,1',
                'format': '0,1,2',
                'codec': '0,1',
            },
            headers=PLAY_HEADERS,
            timeout=15,
        ).json()
        if detail.get('code') != 0:
            return lines
        streams = (
            detail.get('data', {})
            .get('playurl_info', {})
            .get('playurl', {})
            .get('stream', [])
        )
        idx = 0
        for stream in streams:
            for fmt in stream.get('format') or []:
                for codec in fmt.get('codec') or []:
                    base = codec.get('base_url') or ''
                    for info in codec.get('url_info') or []:
                        host = info.get('host') or ''
                        extra = info.get('extra') or ''
                        url = f"{host}{base}{extra}"
                        if url.startswith('http'):
                            idx += 1
                            lines.append((f'{idx}号线路', url))
        return lines

    def detailContent(self, ids):
        did = ids[0]
        result = {}
        videos = []
        lines = self._build_bili_play_lines(did)
        bofang = '#'.join(f"{name}${url}" for name, url in lines if url)
        if not bofang:
            bofang = f"网页嗅探$https://live.bilibili.com/{did}"

        videos.append({
            "vod_id": did,
            "vod_content": '欢迎观看哔哩直播',
            "vod_play_from": '哔哩专线',
            "vod_play_url": bofang
        })

        result['list'] = videos
        return result

    def playerContent(self, flag, id, vipFlags):
        url = (id or '').strip()
        if url.startswith('http') and ('.m3u8' in url or '.flv' in url or 'bilivideo.com' in url):
            return {"parse": 0, "playUrl": '', "url": url, "header": PLAY_HEADERS}
        if url.isdigit():
            lines = self._build_bili_play_lines(url)
            for _, stream in lines:
                if stream:
                    return {"parse": 0, "playUrl": '', "url": stream, "header": PLAY_HEADERS}
            url = f'https://live.bilibili.com/{url}'
        return {"parse": 1, "playUrl": '', "url": url, "header": PLAY_HEADERS}

    def searchContentPage(self, key, quick, pg):
        if pg:
            page = int(pg)
        else:
            page = 1
        url = f'{xurl}/live?keyword={key}&page={str(page)}'
        detail = requests.get(url=url, headers=headerx, timeout=15)
        detail.encoding = "utf-8"
        videos = self._parse_live_cards(detail.text)
        result = {'list': videos}
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, '1')

    def localProxy(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        elif params['type'] == "media":
            return self.proxyMedia(params)
        elif params['type'] == "ts":
            return self.proxyTs(params)
        return None








