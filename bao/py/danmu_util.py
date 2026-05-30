# -*- coding: utf-8 -*-
"""弹幕工具：走 Python/JAR 本地代理拉 XML，不直连外网。"""
import json
import random
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_DANMU_API = "http://43.133.64.9:9321/87654321"
DEFAULT_DANMU_API_BACKUP = (
    "http://danmu04.ifree.fun/87654321",
    "http://danmu05.ifree.fun/87654321",
)
DANMU_API_LABELS = {
    DEFAULT_DANMU_API.rstrip("/"): "主弹幕",
    "http://danmu04.ifree.fun/87654321": "备用4",
    "http://danmu05.ifree.fun/87654321": "备用5",
}
DMKU_API = "https://dmku.hls.one"
_CONFIG_CANDIDATES = (
    "config.json",
    "api.json",
    "../json/config.json",
    "../../json/config.json",
)


def resolve_danmu_api(explicit=None):
    apis = resolve_danmu_apis(explicit)
    return apis[0] if apis else DEFAULT_DANMU_API.rstrip("/")


def resolve_danmu_apis(explicit=None):
    if explicit:
        if isinstance(explicit, (list, tuple)):
            out = [str(x).rstrip("/") for x in explicit if x]
            return out or list(DEFAULT_DANMU_API_BACKUP)
        return [str(explicit).rstrip("/")]
    apis = []
    try:
        import os
        roots = [
            os.getcwd(),
            os.path.dirname(os.path.abspath(__file__)),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "baoge"),
        ]
        for root in roots:
            for name in _CONFIG_CANDIDATES:
                path = os.path.join(root, name)
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    primary = (cfg or {}).get("danmuApi") or ""
                    if primary:
                        apis.append(str(primary).rstrip("/"))
                    backup = (cfg or {}).get("danmuApiBackup") or []
                    if isinstance(backup, list):
                        for item in backup:
                            item = str(item or "").strip().rstrip("/")
                            if item and item not in apis:
                                apis.append(item)
                    if apis:
                        return apis
                except Exception:
                    continue
    except Exception:
        pass
    out = [DEFAULT_DANMU_API.rstrip("/")]
    for item in DEFAULT_DANMU_API_BACKUP:
        if item not in out:
            out.append(item)
    return out

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

# TVBox 播放时会新建 Spider 实例，片名/集数需跨实例缓存
_PLAY_VOD = {}
_DANMU_META = {"name": "", "index": ""}
_JAR_PROXY_BASE = None


def _url_param(text):
    """与独播一致：片名/集数不做 percent 编码。"""
    return str(text or "")


def _cache_play_meta(vod_name, play_url):
    name = clean_name(vod_name)
    if not play_url:
        return
    for block in str(play_url).split("$$$"):
        for item in block.split("#"):
            item = item.strip()
            if not item or "$" not in item:
                continue
            ep, key = item.split("$", 1)
            key = key.strip()
            if not key:
                continue
            _PLAY_VOD[key] = {"name": name, "ep": ep.strip()}


def _lookup_play_meta(play_id):
    pid = str(play_id or "")
    if not pid:
        return {}
    if pid in _PLAY_VOD:
        return _PLAY_VOD[pid]
    fixed = pid.rstrip("/")
    if fixed in _PLAY_VOD:
        return _PLAY_VOD[fixed]
    if fixed + "/" in _PLAY_VOD:
        return _PLAY_VOD[fixed + "/"]
    return {}


def _http_get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_ctx, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def clean_name(name):
    name = re.sub(r"<[^>]+>", "", name or "")
    name = re.sub(r"[（(【<][臻真]彩[）)】>]", "", name)
    name = re.sub(r"[\[\]【】]", "", name)
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
    long_data = (data.get("data") or {}).get("longData")
    if isinstance(long_data, list):
        rows = long_data
    elif isinstance(long_data, dict):
        rows = long_data.get("rows") or []
    else:
        rows = []
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


def resolve_platform_url(vod_name, vod_index="", api_base=DEFAULT_DANMU_API):
    name = clean_name(vod_name)
    if not name:
        return ""
    episode = parse_episode(vod_index or vod_name)
    link = search_360_playlink(name, episode)
    if link:
        return link
    if episode != 1:
        return search_360_playlink(name, 1)
    return ""


def build_direct_danmu_url(vod_name, vod_index="", api_base=DEFAULT_DANMU_API):
    """直连 XML（仅调试用，播放器请走 build_danmu_url）。"""
    link = resolve_platform_url(vod_name, vod_index, api_base)
    if not link:
        return ""
    return (
        f"{api_base.rstrip('/')}/api/v2/comment?url="
        + urllib.parse.quote(link)
        + "&format=xml"
    )


def api_source_label(api_base):
    base = str(api_base or "").strip().rstrip("/")
    if not base:
        return ""
    if base in DANMU_API_LABELS:
        return DANMU_API_LABELS[base]
    if "danmu04" in base:
        return "备用4"
    if "danmu05" in base:
        return "备用5"
    return "主弹幕"


def notify_danmu_success(source=""):
    msg = "弹幕加载成功"
    if source:
        msg = f"弹幕加载成功（{source}）"
    for call in (
        lambda: __import__("com.github.catvod.spider.merge.m.I", fromlist=["I"]).i(msg),
        lambda: __import__("com.github.catvod.spider.merge.AB.o.E", fromlist=["E"]).b(msg),
    ):
        try:
            call()
            return
        except Exception:
            continue


def fetch_xml_by_video_url(video_url, api_base=None):
    if not video_url:
        return ""
    bases = resolve_danmu_apis(api_base)
    for base in bases:
        url = (
            f"{base.rstrip('/')}/api/v2/comment?url="
            + urllib.parse.quote(video_url)
            + "&format=xml"
        )
        try:
            text = _http_get(url, 60)
            if text and "<d " in text:
                return text, api_source_label(base)
        except Exception:
            continue
    return "", ""


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


def fetch_danmu_xml(vod_name, vod_index="", api_base=None):
    name = clean_name(vod_name)
    if not name:
        return empty_xml(), ""
    link = resolve_platform_url(name, vod_index)
    if link:
        xml, source = fetch_xml_by_video_url(link, api_base)
        if xml:
            return xml, source
        xml = fetch_dmku_json(link)
        if xml:
            return xml, "弹幕库"
    return empty_xml(), ""


def _discover_jar_proxy_base(force=False):
    """发现 JAR Proxy 端口（与 Proxy.smali 一致），勿用 Python getProxyUrl。"""
    global _JAR_PROXY_BASE
    if _JAR_PROXY_BASE and not force:
        return _JAR_PROXY_BASE
    for port in range(9978, 10000):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/proxy?do=ck",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                if (resp.read() or b"").decode("utf-8", "replace").strip() == "ok":
                    _JAR_PROXY_BASE = f"http://127.0.0.1:{port}/proxy"
                    return _JAR_PROXY_BASE
        except Exception:
            continue
    _JAR_PROXY_BASE = "http://127.0.0.1:9978/proxy"
    return _JAR_PROXY_BASE


def _save_danmu_meta(name, ep):
    name = clean_name(name)
    ep = str(ep or "").strip()
    if name:
        _DANMU_META["name"] = name
    if ep:
        _DANMU_META["index"] = ep
    try:
        jl = __import__("com.github.catvod.spider.merge.m.l", fromlist=["l"])
        if name:
            jl.a("danmuvodname", name)
            jl.a("searchvodname", name)
        if ep:
            jl.a("danmuvodindex", ep)
    except Exception:
        pass


def _read_java_stream(stream):
    if stream is None:
        return ""
    try:
        buf = bytearray()
        while True:
            chunk = stream.read(8192)
            if chunk is None:
                break
            if isinstance(chunk, int):
                if chunk < 0:
                    break
                buf.append(chunk)
                continue
            if len(chunk) == 0:
                break
            buf.extend(chunk)
        return bytes(buf).decode("utf-8", "replace")
    except Exception:
        return ""


def _jar_appdanmu_xml(vod_name, vod_index=""):
    """TV 端直接调 JAR Danmu.AppDanmu，与独播/瓜子 JAR 同源逻辑。"""
    name = clean_name(vod_name) or _DANMU_META.get("name", "")
    ep = str(vod_index or _DANMU_META.get("index", "") or "")
    if not name:
        return None
    try:
        from java.util import HashMap
        from com.github.catvod.spider.Danmu import Danmu

        params = HashMap()
        params.put("vodName", name)
        params.put("vodIndex", ep)
        hit = Danmu.AppDanmu(params)
        if not hit or len(hit) < 3:
            return None
        xml = _read_java_stream(hit[2])
        return xml if xml else empty_xml()
    except Exception:
        return None


def _fetch_appdanmu_via_jar_http(vod_name, vod_index=""):
    base = _discover_jar_proxy_base()
    name = _url_param(clean_name(vod_name) or _DANMU_META.get("name", ""))
    ep = _url_param(vod_index or _DANMU_META.get("index", ""))
    if not name:
        return empty_xml()
    url = f"{base}?do=appdanmu&vodName={name}&vodIndex={ep}"
    try:
        text = _http_get(url, 120)
        if text:
            return text
    except Exception:
        pass
    return empty_xml()


def _proxy_append(base, query):
    base = (base or "").strip()
    if not base:
        return ""
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{query}"


def _jar_proxy_base(spider=None):
    return _discover_jar_proxy_base()


def build_py_danmu_url(spider, vod_name, vod_index=""):
    """Python 源：走 getProxyUrl + type=danmu，由 localProxy 返回 XML。"""
    name = _url_param(clean_name(vod_name))
    ep = _url_param(vod_index or "")
    try:
        base = spider.getProxyUrl() or ""
    except Exception:
        base = ""
    if base and "/proxy" in base:
        return _proxy_append(base, f"type=danmu&vodName={name}&vodIndex={ep}")
    return ""


def build_appdanmu_url(spider, vod_name, vod_index=""):
    """JAR 源：走 /proxy?do=appdanmu（与独播一致）。"""
    base = _jar_proxy_base(spider)
    name = _url_param(clean_name(vod_name))
    ep = _url_param(vod_index or "")
    return f"{base}?do=appdanmu&vodName={name}&vodIndex={ep}"


def build_danmu_url(spider, vod_name, vod_index="", api_base=DEFAULT_DANMU_API):
    """与独播一致：统一走 JAR /proxy?do=appdanmu&vodName=&vodIndex="""
    return build_appdanmu_url(spider, vod_name, vod_index)


def attach_danmaku(spider, result, vod_name, vod_index=""):
    name = clean_name(vod_name)
    if not isinstance(result, dict) or not name:
        return result
    ep = str(vod_index or "").strip() or str(parse_episode(vod_index or name))
    _save_danmu_meta(name, ep)
    url = build_danmu_url(spider, name, ep)
    if not url:
        return result
    result["danmaku"] = url
    result["danmu"] = url
    return result


def init_spider_cache(spider):
    if not hasattr(spider, "_vod_name"):
        spider._vod_name = ""
    if not hasattr(spider, "_ep_map"):
        spider._ep_map = {}


def remember_playlist(spider, vod_name="", play_url=""):
    init_spider_cache(spider)
    if vod_name:
        spider._vod_name = clean_name(vod_name)
    spider._ep_map = {}
    _cache_play_meta(vod_name, play_url)
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
    meta = _lookup_play_meta(play_id)
    ep = meta.get("ep") or spider._ep_map.get(play_id) or spider._ep_map.get(str(play_id)) or flag or ""
    name = meta.get("name") or spider._vod_name
    if not name and isinstance(flag, str) and flag:
        name = clean_name(re.sub(r"线路\d+", "", flag))
    if not name and isinstance(result, dict):
        for key in ("vod_name", "name", "title"):
            val = result.get(key)
            if val:
                name = clean_name(str(val))
                break
    return attach_danmaku(spider, result, name, ep)


def _is_danmu_request(params):
    do = (params or {}).get("do") or (params or {}).get("type") or ""
    return do in ("danmu", "appdanmu")


def handle_danmu_proxy(params, api_base=None):
    if not _is_danmu_request(params):
        return None
    name = (
        params.get("vodName")
        or params.get("vodname")
        or params.get("name")
        or _DANMU_META.get("name")
        or ""
    )
    ep = (
        params.get("vodIndex")
        or params.get("vodindex")
        or params.get("index")
        or _DANMU_META.get("index")
        or ""
    )
    xml = _jar_appdanmu_xml(name, ep)
    if xml is None:
        xml = _fetch_appdanmu_via_jar_http(name, ep)
    if not xml or "<d " not in xml:
        xml, _source = fetch_danmu_xml(name, ep, api_base=api_base)
    return [200, "application/xml", xml or empty_xml()]


def proxy_with_danmu(params, fallback=None, api_base=DEFAULT_DANMU_API):
    hit = handle_danmu_proxy(params, api_base=api_base)
    if hit:
        return hit
    return fallback(params) if fallback else None
