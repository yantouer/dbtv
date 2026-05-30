# -*- coding: utf-8 -*-
"""弹幕工具：360影视 + danmu_api 公共接口，供 Python 源 localProxy 使用。"""
import json
import random
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_DANMU_API = "https://pizazz.us.ci/1314"
DMKU_API = "https://dmku.hls.one"

SKIP_WORDS = (
    "请遵守弹幕礼仪",
    "官方弹幕库",
    "未传入链接调用",
    "弹幕列队",
    "火花剧场",
    "云烟小助手",
    "微信公众号",
)

COLORS = (
    "16711680", "16776960", "65280", "255", "16711935", "8388736",
    "16753920", "65535", "16777215", "16761087", "16777087",
)

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _http_get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_ctx, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def clean_name(name):
    name = re.sub(r"[（(【<][臻真]彩[）)】>]", "", name or "")
    return name.strip()


def parse_episode(text):
    text = text or ""
    text = re.sub(r"\[.*?\]", "", text)
    m = re.search(r"第(\d+)[集话]", text)
    if m:
        return int(m.group(1))
    m = re.search(r"S\d+E(\d{2,3})", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{4})[-._]?(\d{2})[-._]?(\d{2})", text)
    if m:
        return int(m.group(1) + m.group(2) + m.group(3))
    m = re.search(r"(\d+)", text.split(".")[0])
    if m:
        return int(m.group(1))
    return 1


def _norm_platform_url(url):
    if not url:
        return ""
    url = url.strip()
    if "v.qq.com" in url and ".html" in url:
        idx = url.find(".html")
        return url[: idx + len(".html")]
    if "www.iqiyi.com" in url and ".html" in url:
        idx = url.find(".html")
        return url[: idx + len(".html")]
    if "www.mgtv.com" in url and ".html" in url:
        idx = url.find(".html")
        return url[: idx + len(".html")]
    if "v.youku.com" in url and "vid=" in url:
        start = url.find("vid=") + 4
        end = url.find("&", start)
        if end == -1:
            end = len(url)
        vid = url[start:end]
        if vid:
            return f"https://v.youku.com/v_show/id_{vid}.html"
    return url


def search_360_playlink(name, episode=1):
    url = (
        "https://api.so.360kan.com/index?force_v=1&kw="
        + urllib.parse.quote(name)
        + "&from=&pageno=1&v_ap=1&tab=all"
    )
    try:
        data = json.loads(_http_get(url, 20))
    except Exception:
        return ""
    rows = data.get("data", {}).get("longData", {}).get("rows", [])
    if not rows:
        return ""
    for cat in ("电视剧", "电影", "动漫"):
        for row in rows:
            title = row.get("titleTxt") or row.get("title") or ""
            title = re.sub(r"<[^>]+>", "", title)
            if cat != row.get("cat_name"):
                continue
            if name not in title and title not in name:
                continue
            if cat == "电影":
                links = row.get("playlinks") or {}
                for key in ("qq", "qiyi", "youku", "imgo", "bilibili1"):
                    if links.get(key):
                        return _norm_platform_url(links[key])
            else:
                series = row.get("seriesPlaylinks") or []
                idx = max(episode, 1) - 1
                if 0 <= idx < len(series):
                    ep_url = (series[idx] or {}).get("url", "")
                    if ep_url:
                        return _norm_platform_url(ep_url)
    row = rows[0]
    cat = row.get("cat_name", "")
    if cat == "电影":
        links = row.get("playlinks") or {}
        for key in ("qq", "qiyi", "youku", "imgo"):
            if links.get(key):
                return _norm_platform_url(links[key])
    series = row.get("seriesPlaylinks") or []
    idx = max(episode, 1) - 1
    if 0 <= idx < len(series):
        return _norm_platform_url((series[idx] or {}).get("url", ""))
    return ""


def fetch_xml_by_video_url(video_url, api_base=DEFAULT_DANMU_API):
    if not video_url:
        return ""
    url = (
        f"{api_base.rstrip('/')}/api/v2/comment?url="
        + urllib.parse.quote(video_url)
        + "&format=xml"
    )
    try:
        text = _http_get(url, 60)
        if text and "<d " in text:
            return text
    except Exception:
        pass
    return ""


def _json_danmuku_to_xml(payload):
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except Exception:
        return ""
    arr = data.get("danmuku") if isinstance(data, dict) else None
    if not arr:
        return ""
    root = ET.Element("i")
    for item in arr:
        if not isinstance(item, (list, tuple)) or len(item) < 5:
            continue
        text = str(item[4] or "")
        if any(x in text for x in SKIP_WORDS):
            continue
        d = ET.SubElement(root, "d")
        color = random.choice(COLORS)
        d.set("p", f"{item[0]},1,25,{color}")
        d.text = text
    if not list(root):
        return ""
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def fetch_dmku_json(video_url):
    url = f"{DMKU_API}/?ac=dm&url={urllib.parse.quote(video_url)}"
    try:
        text = _http_get(url, 90)
        if '"danmuku"' in text:
            return _json_danmuku_to_xml(text)
    except Exception:
        pass
    return ""


def empty_xml():
    return '<?xml version="1.0" encoding="UTF-8"?><i></i>'


def fetch_danmu_xml(vod_name, vod_index="", api_base=DEFAULT_DANMU_API):
    name = clean_name(vod_name)
    if not name:
        return empty_xml()
    episode = parse_episode(vod_index or vod_name)
    video_url = search_360_playlink(name, episode)
    if video_url:
        xml = fetch_xml_by_video_url(video_url, api_base)
        if xml:
            return xml
        xml = fetch_dmku_json(video_url)
        if xml:
            return xml
    if episode != 1:
        video_url = search_360_playlink(name, 1)
        if video_url:
            xml = fetch_xml_by_video_url(video_url, api_base)
            if xml:
                return xml
    return empty_xml()


def danmu_proxy_url(spider, vod_name, vod_index=""):
    base = spider.getProxyUrl()
    return (
        f"{base}&do=danmu&vodName={urllib.parse.quote(str(vod_name or ''))}"
        f"&vodIndex={urllib.parse.quote(str(vod_index or ''))}"
    )


def attach_danmaku(spider, result, vod_name, vod_index=""):
    if isinstance(result, dict) and vod_name:
        result["danmaku"] = danmu_proxy_url(spider, vod_name, vod_index)
    return result


def init_spider_cache(spider):
    if not hasattr(spider, "_vod_name"):
        spider._vod_name = ""
    if not hasattr(spider, "_ep_map"):
        spider._ep_map = {}


def remember_playlist(spider, vod_name="", play_url=""):
    init_spider_cache(spider)
    if vod_name:
        spider._vod_name = str(vod_name).strip()
    spider._ep_map = {}
    if not play_url:
        return
    for block in str(play_url).split("$$$"):
        for item in block.split("#"):
            item = item.strip()
            if not item or "$" not in item:
                continue
            ep, key = item.split("$", 1)
            spider._ep_map[key.strip()] = ep.strip()


def remember_from_vod(spider, vod):
    if isinstance(vod, dict):
        remember_playlist(spider, vod.get("vod_name", ""), vod.get("vod_play_url", ""))


def attach_player(spider, result, play_id, flag=""):
    init_spider_cache(spider)
    ep = spider._ep_map.get(play_id, flag)
    return attach_danmaku(spider, result, spider._vod_name, ep)


def proxy_with_danmu(params, fallback=None, api_base=DEFAULT_DANMU_API):
    hit = handle_danmu_proxy(params, api_base=api_base)
    if hit:
        return hit
    return fallback(params) if fallback else None


def handle_danmu_proxy(params, api_base=DEFAULT_DANMU_API):
    if (params or {}).get("do") != "danmu":
        return None
    xml = fetch_danmu_xml(
        params.get("vodName") or params.get("vodname") or "",
        params.get("vodIndex") or params.get("vodindex") or "",
        api_base=api_base,
    )
    return [200, "application/xml", xml]
