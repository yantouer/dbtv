# coding=utf-8
# !/usr/bin/python
"""厂长资源 — 与 CSP czzymovie 同源，支持 init(extend) 传入站点域名。"""
import base64
import re
import sys

sys.path.append("..")
from base.spider import Spider
from Crypto.Cipher import AES


class Spider(Spider):

    def getName(self):
        return "厂长资源"

    def init(self, extend=""):
        host = (extend or "https://www.czzymovie.com").strip().rstrip("/")
        if host and not host.startswith("http"):
            host = "https://" + host
        self.host = host
        self._vod_name = ""
        self._ep_map = {}
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        try:
            rsp = self.fetch(self.host, headers=self.headers, timeout=12)
            cookies = rsp.headers.get("Set-Cookie") or rsp.headers.get("set-cookie")
            if cookies:
                self.headers["Cookie"] = cookies.split(";")[0]
        except Exception:
            pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _classes(self):
        return [
            {"type_id": "movie_bt", "type_name": "全部影片"},
            {"type_id": "zuixindianying", "type_name": "最新电影"},
            {"type_id": "dbtop250", "type_name": "豆瓣Top250"},
            {"type_id": "dyy", "type_name": "电影"},
            {"type_id": "guochanju", "type_name": "国产剧"},
            {"type_id": "mj", "type_name": "美剧"},
            {"type_id": "hj", "type_name": "韩剧"},
            {"type_id": "rj", "type_name": "日剧"},
            {"type_id": "fjj", "type_name": "番剧"},
        ]

    def _path(self, tid):
        special = {
            "dyy": "movie_bt_series/dyy",
            "guochanju": "movie_bt_series/guochanju",
            "mj": "movie_bt_series/mj",
            "hj": "movie_bt_series/hj",
            "rj": "movie_bt_series/rj",
            "hwj": "movie_bt_series/hwj",
            "fjj": "movie_bt_view_cat/fjj",
        }
        return special.get(tid, tid)

    def homeContent(self, filter):
        return {"class": self._classes()}

    def homeVideoContent(self):
        try:
            rsp = self.fetch(self.host, headers=self.headers, timeout=15)
            return {"list": self._parse_list(rsp.text, 24)}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        path = self._path(tid)
        url = f"{self.host}/{path}" if page == "1" else f"{self.host}/{path}/page/{page}"
        rsp = self.fetch(url, headers=self.headers, timeout=15)
        videos = self._parse_list(rsp.text)
        return {
            "list": videos,
            "page": int(page),
            "pagecount": 9999,
            "limit": 90,
            "total": 999999,
        }

    def _parse_list(self, html, limit=90):
        root = self.html(self.cleanText(html))
        nodes = (
            root.xpath("//div[contains(@class,'bt_img')]//li")
            or root.xpath("//div[contains(@class,'mi_cont')]//ul/li")
            or root.xpath("//div[contains(@class,'mi_btcon')]//ul/li")
        )
        videos = []
        seen = set()
        for node in nodes:
            hrefs = node.xpath(".//a[contains(@href,'/movie/')]/@href")
            if not hrefs:
                continue
            sid = self.regStr(hrefs[0], r"/movie/(\S+?)(?:\.html)?")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            name = (
                node.xpath(".//a/img/@alt")
                or node.xpath(".//a/@title")
                or node.xpath(".//a/text()")
                or [""]
            )[0].strip()
            pic = (
                node.xpath(".//a/img/@data-original")
                or node.xpath(".//a/img/@src")
                or [""]
            )[0]
            mark = (node.xpath(".//span/text()") or [""])[0].strip()
            videos.append(
                {
                    "vod_id": sid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": mark,
                }
            )
            if limit and len(videos) >= limit:
                break
        return videos

    def detailContent(self, array):
        tid = array[0]
        url = f"{self.host}/movie/{tid}.html"
        rsp = self.fetch(url, headers=self.headers, timeout=15)
        root = self.html(self.cleanText(rsp.text))
        node = root.xpath("//div[@class='dyxingq']")
        if not node:
            return {"list": []}
        node = node[0]
        pic = (node.xpath(".//div[@class='dyimg fl']/img/@src") or [""])[0]
        title = (node.xpath(".//h1/text()") or [""])[0]
        detail = (root.xpath(".//div[@class='yp_context']//p/text()") or [""])[0]
        vod = {
            "vod_id": tid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": detail,
            "vod_play_from": "厂长",
            "vod_play_url": "",
        }
        play_items = []
        for vl in root.xpath("//div[@class='paly_list_btn']"):
            for a in vl.xpath("./a"):
                href = a.xpath("./@href")[0]
                name = a.xpath("./text()")[0].strip()
                pid = self.regStr(href, r"/v_play/(\S+?)(?:\.html)?")
                if pid:
                    play_items.append(f"{name}${pid}")
        vod["vod_play_url"] = "#".join(play_items)
        self._vod_name = title
        self._ep_map = {pid: name for name, pid in [x.split("$", 1) for x in play_items if "$" in x]}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/xssearch?q={key}"
        rsp = self.fetch(url, headers=self.headers, timeout=15)
        root = self.html(self.cleanText(rsp.text))
        videos = []
        for vod in root.xpath("//div[contains(@class,'mi_ne_kd')]/ul/li/a"):
            name = vod.xpath("./img/@alt")[0]
            pic = vod.xpath("./img/@data-original") or vod.xpath("./img/@src")
            pic = pic[0] if pic else ""
            href = vod.xpath("./@href")[0]
            sid = self.regStr(href, r"movie/(\S+?)(?:\.html)?")
            remark = (vod.xpath('./div[@class="jidi"]/span/text()') or ["全1集"])[0]
            videos.append(
                {
                    "vod_id": sid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                }
            )
        return {"list": videos}

    def parseCBC(self, enc, key, iv):
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
        msg = cipher.decrypt(enc)
        return msg[0 : -msg[-1]]

    def playerContent(self, flag, id, vipFlags):
        url = f"{self.host}/v_play/{id}.html"
        rsp = self.fetch(url, headers=self.headers, timeout=15)
        html = rsp.text
        pat = (
            r'\\"([^\\"]+)\\";var [\d\w]+=function dncry.*'
            r'md5\.enc\.Utf8\.parse\\\(\\"([\d\w]+)\\".*'
            r'md5\.enc\.Utf8\.parse\(([\\d]+)\)'
        )
        content = self.regStr(html, pat)
        if not content:
            return {"parse": 0, "playUrl": "", "url": ""}
        key = self.regStr(html, pat, 2)
        iv = self.regStr(html, pat, 3)
        decontent = self.parseCBC(base64.b64decode(content), key, iv).decode()
        play_url = self.regStr(decontent, r'video: \{url: \\"([^\\"]+)\\"')
        result = {"parse": 0, "playUrl": "", "url": play_url, "header": self.headers}
        try:
            from danmu_util import attach_danmaku
            attach_danmaku(self, result, self._vod_name, self._ep_map.get(id, flag))
        except Exception:
            pass
        return result

    def localProxy(self, params):
        try:
            from danmu_util import handle_danmu_proxy
            return handle_danmu_proxy(params)
        except Exception:
            return None
