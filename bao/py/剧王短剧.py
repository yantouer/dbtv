# coding=utf-8
# !/usr/bin/python

"""

作者 丢丢喵推荐 🚓 内容均从互联网收集而来 仅供交流学习使用 版权归原创者所有 如侵犯了您的权益 请通知作者 将及时删除侵权内容
                    ====================Diudiumiao====================

"""

from urllib.parse import quote, urljoin
from base.spider import Spider
from bs4 import BeautifulSoup
import requests
import json
import re
import sys

sys.path.append('..')

xurl = "https://taijuwang.com"

headerx = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://taijuwang.com/',
}


class Spider(Spider):
    global xurl
    global headerx

    def getName(self):
        return "首页"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _get(self, url):
        res = requests.get(url=url, headers=headerx, timeout=20, allow_redirects=True)
        res.encoding = "utf-8"
        return res.text

    def _abs(self, path):
        if not path:
            return path
        if path.startswith('http'):
            return path
        return urljoin(xurl, path)

    def _is_hot_link(self, node):
        parent = node
        for _ in range(6):
            if not parent:
                break
            classes = parent.get('class') or []
            if 'hot-bottom' in classes or 'hot-content' in classes:
                return True
            parent = parent.parent
        return False

    def _list_vods(self, html):
        doc = BeautifulSoup(html, "lxml")
        videos = []
        seen = set()
        for a in doc.select("a[href*='/v/']"):
            href = a.get('href', '')
            if not re.match(r'/v/\d+\.html', href):
                continue
            if href in seen or self._is_hot_link(a):
                continue
            seen.add(href)
            card = a.find_parent('article') or a.find_parent('li') or a.find_parent('div')
            img = (card or a).find('img')
            name = ''
            if img:
                name = (img.get('alt') or img.get('title') or '').strip()
            if not name:
                name = (a.get('title') or a.text or '').strip()
            pic = ''
            if img:
                pic = img.get('src') or img.get('data-src') or ''
            if pic and not pic.startswith('http'):
                pic = self._abs(pic)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": '',
            })
        return videos

    def _parse_play_url(self, html):
        m = re.search(r'const\s+playUrls\s*=\s*(\{[^;]+\})', html)
        if not m:
            m = re.search(r'"([^"]*m3u8[^"]*)"\s*:\s*"([^"]+)"', html)
            if m:
                return m.group(2).replace('\\/', '/')
            return ''
        try:
            play_urls = json.loads(m.group(1))
        except Exception:
            return ''
        for key in ('lzm3u8', 'ffm3u8', 'dyttm3u8', 'wjm3u8', 'modum3u8', 'gsm3u8'):
            if key in play_urls and play_urls[key]:
                return play_urls[key].replace('\\/', '/')
        for val in play_urls.values():
            if val and 'm3u8' in val:
                return val.replace('\\/', '/')
        return ''

    def homeContent(self, filter):
        result = {"class": []}
        res = self._get(xurl + "/all/")
        doc = BeautifulSoup(res, "lxml")
        seen = set()
        for a in doc.find_all('a', href=True):
            href = a['href']
            name = a.text.strip()
            if not re.match(r'/[\w-]+/$', href):
                continue
            if href in ('/', '/all/', '/history/') or href in seen:
                continue
            if not name or len(name) > 15:
                continue
            seen.add(href)
            result["class"].append({"type_id": href, "type_name": name})
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        cid = cid if cid.startswith('http') else self._abs(cid)
        if not cid.endswith('/'):
            cid += '/'
        url = cid if page <= 1 else cid + f'?page={page}'
        videos = self._list_vods(self._get(url))
        return {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def detailContent(self, ids):
        did = ids[0]
        if 'http' not in did:
            did = self._abs(did)
        res = self._get(did)
        doc = BeautifulSoup(res, "lxml")

        content = ''
        remarks = ''
        year = ''
        for item in doc.select('.info-item'):
            text = item.get_text(' ', strip=True)
            if text.startswith('简介'):
                content = text.replace('简介：', '').replace('简介:', '').strip()
            elif text.startswith('状态'):
                remarks = text.replace('状态：', '').replace('状态:', '').strip()
        tag = doc.select_one('.info-tag')
        if tag:
            year = tag.get_text(' ', strip=True)

        bofang = []
        for ep in doc.select('.ep-all a.list-ep'):
            ep_id = ep.get('href', '')
            ep_name = ep.text.strip() or ep.get('title', '')
            if ep_id:
                bofang.append(f"{ep_name}${ep_id}")

        if not bofang:
            play_path = re.sub(r'/v/(\d+)\.html', r'/p/\1/1.html', did.replace(xurl, ''))
            if play_path != did:
                bofang.append(f"播放${play_path}")

        title = ''
        h1 = doc.select_one('h1') or doc.select_one('.video-title')
        if h1:
            title = h1.get_text(' ', strip=True)

        videos = [{
            "vod_id": did,
            "vod_name": title,
            "vod_remarks": remarks,
            "vod_year": year,
            "vod_content": content,
            "vod_play_from": "剧王",
            "vod_play_url": '#'.join(bofang),
        }]
        try:
            from danmu_util import remember_from_vod
            remember_from_vod(self, videos[0])
        except Exception:
            pass
        return {'list': videos}

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith('http') else self._abs(id)
        res = self._get(play_url)
        url = self._parse_play_url(res)
        result = {
            "parse": 0,
            "playUrl": '',
            "url": url,
            "header": headerx,
        }
        try:
            from danmu_util import attach_player
            attach_player(self, result, id, flag)
        except Exception:
            pass
        return result

    def searchContentPage(self, key, quick, pg):
        page = int(pg) if pg else 1
        if page <= 1:
            url = xurl + '/?s=' + quote(key)
        else:
            url = xurl + f'/page/{page}/?s=' + quote(key)
        videos = self._list_vods(self._get(url))
        return {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, '1')

    def localProxy(self, params):
        try:
            from danmu_util import proxy_with_danmu
            hit = proxy_with_danmu(params, self._local_proxy_media)
            if hit:
                return hit
        except Exception:
            pass
        return self._local_proxy_media(params)

    def _local_proxy_media(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        elif params['type'] == "media":
            return self.proxyMedia(params)
        elif params['type'] == "ts":
            return self.proxyTs(params)
        return None
