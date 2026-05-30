# -*- coding: utf-8 -*-
"""弹幕工具：走 Python/JAR 本地代理拉 XML，不直连外网。"""
import json
import hashlib
import random
import re
import ssl
import time
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
# 方案 B：Python 源不内嵌弹幕；弹幕由 JAR 源或播放器「搜索弹幕」+ danmuApi 承担
PY_ATTACH_DANMU = False
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
_VOD_ID_NAME = {}
_EP_BY_KEY = {}
_DANMU_URL_BY_KEY = {}
_LOCAL_PORT = 0
_JAR_PROXY_BASE = "http://127.0.0.1:9978/proxy"


def _url_param(text):
    """与独播一致：片名/集数不做 percent 编码。"""
    return str(text or "")


def _norm_play_key(key):
    return urllib.parse.unquote(str(key or "").strip())


def _play_key_id(key):
    text = _norm_play_key(key)
    if not text:
        return ""
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def _cache_ttl():
    return int(time.time()) + 86400 * 7


def _unwrap_cache_value(val):
    if val is None:
        return ""
    if isinstance(val, dict):
        exp = val.get("expiresAt")
        if exp is not None and int(exp) < int(time.time()):
            return ""
        v = val.get("v")
        if v is not None:
            return str(v)
        return ""
    text = str(val).strip()
    if not text or text in ("failed", "None"):
        return ""
    if text.startswith("{") and text.endswith("}"):
        try:
            return _unwrap_cache_value(json.loads(text))
        except Exception:
            pass
    return text


def _spider_cache_get(spider, key, default=""):
    if not key:
        return default
    if spider:
        try:
            val = spider.getCache(str(key))
            text = _unwrap_cache_value(val)
            if text:
                return text
        except Exception:
            pass
    http_val = _local_http_cache_get(str(key))
    if http_val:
        text = _unwrap_cache_value(http_val)
        if text:
            return text
    return default


def _spider_cache_set(spider, key, value, ttl=None):
    if not key or value in (None, ""):
        return
    payload = {"v": str(value), "expiresAt": ttl or _cache_ttl()}
    if spider:
        try:
            spider.setCache(str(key), payload)
        except Exception:
            pass
    try:
        _local_http_cache_set(str(key), json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


def _resolve_spider_proxy(spider):
    """FongMi Python: proxy://?do=py；旧版 TVBox: http://127.0.0.1:9978/proxy?site=xxx"""
    if not spider:
        return ""
    for call in (
        lambda: spider.getProxyUrl(),
        lambda: spider.getProxyUrl(True),
        lambda: spider.getProxyUrl(False),
    ):
        try:
            raw = str(call() or "").strip()
            if raw:
                return raw
        except Exception:
            continue
    return ""


def _ensure_local_port():
    global _LOCAL_PORT
    if _LOCAL_PORT:
        return _LOCAL_PORT
    for port in range(9978, 9999):
        try:
            _http_get(f"http://127.0.0.1:{port}/device", timeout=1)
            _LOCAL_PORT = port
            return port
        except Exception:
            continue
    _LOCAL_PORT = 9978
    return _LOCAL_PORT


def _local_http_cache_set(key, value, rule=""):
    if not key or value in (None, ""):
        return
    try:
        port = _ensure_local_port()
        q = urllib.parse.urlencode({"do": "set", "key": str(key), "rule": rule or ""})
        url = f"http://127.0.0.1:{port}/cache?{q}"
        data = urllib.parse.urlencode({"value": str(value)}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req, context=_ctx, timeout=3)
    except Exception:
        pass


def _local_http_cache_get(key, rule=""):
    if not key:
        return ""
    try:
        port = _ensure_local_port()
        args = {"do": "get", "key": str(key)}
        if rule:
            args["rule"] = str(rule)
        q = urllib.parse.urlencode(args)
        text = _http_get(f"http://127.0.0.1:{port}/cache?{q}", timeout=3)
        if text and text not in ("failed", "None"):
            return str(text).strip()
    except Exception:
        pass
    return ""


def _load_media_title():
    try:
        port = _ensure_local_port()
        text = _http_get(f"http://127.0.0.1:{port}/media", timeout=2)
        if text and text.strip().startswith("{"):
            data = json.loads(text)
            title = clean_name(data.get("title") or "")
            if title:
                return title
    except Exception:
        pass
    return ""


def resolve_danmu_name(spider, play_id="", flag="", explicit=""):
    name = clean_name(explicit)
    if name:
        return name
    if spider:
        name = clean_name(getattr(spider, "_vod_name", "") or "")
        if name:
            return name
    name = _spider_cache_get(spider, "current_vod_name")
    if name:
        return clean_name(name)
    meta = _lookup_play_meta(play_id)
    if meta.get("name"):
        return clean_name(meta["name"])
    vid = _vod_id_from_play_id(play_id)
    name = load_vod_name(vid, spider)
    if name:
        return name
    name = _spider_cache_get(spider, "danmu_vod_name")
    if name:
        return clean_name(name)
    name = _load_java_danmu_name()
    if name:
        return name
    name = _load_media_title()
    if name:
        _spider_cache_set(spider, "current_vod_name", name)
        return clean_name(name)
    if isinstance(flag, str) and flag and not re.match(r"^线路?\d+$", flag.strip()):
        guess = clean_name(re.sub(r"线路\d+", "", flag))
        if guess and not re.match(r"^第?\d+集?$", guess):
            return guess
    for part in str(play_id or "").split("&"):
        if part.startswith("dmvn="):
            return clean_name(urllib.parse.unquote(part[5:]))
    return ""


def resolve_danmu_episode(spider, play_id="", flag="", explicit=""):
    ep = str(explicit or "").strip()
    if ep:
        return ep
    meta = _lookup_play_meta(play_id)
    if meta.get("ep"):
        return str(meta["ep"])
    ep = load_ep_title(play_id, spider)
    if ep:
        return ep
    if spider:
        ep = (
            spider._ep_map.get(play_id)
            or spider._ep_map.get(str(play_id))
            or spider._ep_map.get(_norm_play_key(play_id))
        )
        if ep:
            return str(ep)
    if isinstance(flag, str) and flag.strip():
        return flag.strip()
    return _load_java_danmu_index() or "1"


def build_direct_player_danmu_url(vod_name, vod_index=""):
    """外网 XML 直连，不依赖 proxy://，OK影视/FongMi 设置里能显示。"""
    name = clean_name(vod_name)
    if not name:
        return ""
    try:
        link = resolve_platform_url(name, vod_index)
        if not link:
            return ""
        base = resolve_danmu_api()
        return (
            f"{base.rstrip('/')}/api/v2/comment?url="
            + urllib.parse.quote(link, safe="")
            + "&format=xml"
        )
    except Exception:
        return ""


def _cache_danmu_url(play_key, url, spider=None):
    pid = _play_key_id(play_key)
    if not pid or not url:
        return
    _DANMU_URL_BY_KEY[pid] = url
    _spider_cache_set(spider, f"danmu_url_{pid}", url)


def load_danmu_url(play_id, spider=None):
    pid = _play_key_id(play_id)
    if not pid:
        return ""
    if pid in _DANMU_URL_BY_KEY:
        return _DANMU_URL_BY_KEY[pid]
    url = _spider_cache_get(spider, f"danmu_url_{pid}")
    if url:
        return url
    return _unwrap_cache_value(_local_http_cache_get(f"danmu_url_{pid}"))


def _cache_ep_by_key(play_key, ep_title, spider=None):
    pid = _play_key_id(play_key)
    ep = str(ep_title or "").strip()
    if not pid or not ep:
        return
    _EP_BY_KEY[pid] = ep
    _spider_cache_set(spider, f"danmu_ep_{pid}", ep)


def load_ep_title(play_id, spider=None):
    pid = _play_key_id(play_id)
    if not pid:
        return ""
    if pid in _EP_BY_KEY:
        return _EP_BY_KEY[pid]
    return _spider_cache_get(spider, f"danmu_ep_{pid}")


def _cache_play_meta(vod_name, play_url, spider=None):
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
            meta = {"name": name, "ep": ep.strip()}
            for variant in {key, _norm_play_key(key), key.replace("&amp;", "&")}:
                if variant:
                    _PLAY_VOD[variant] = meta
            _cache_ep_by_key(key, ep.strip(), spider)


def _lookup_play_meta(play_id):
    pid = _norm_play_key(play_id)
    for key in (pid, pid.rstrip("/"), pid + "/"):
        if key in _PLAY_VOD:
            return _PLAY_VOD[key]
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
    """返回 JAR 代理地址，不阻塞扫描端口。"""
    return _jar_proxy_base()


def _jar_proxy_base(spider=None):
    global _JAR_PROXY_BASE
    try:
        proxy = __import__("com.github.catvod.spider.Proxy", fromlist=["Proxy"])
        url = str(proxy.getUrl() or "")
        if "/proxy" in url:
            base = url.split("?")[0]
            _JAR_PROXY_BASE = base
            return base
    except Exception:
        pass
    if _JAR_PROXY_BASE:
        return _JAR_PROXY_BASE.split("?")[0] if "?" in _JAR_PROXY_BASE else _JAR_PROXY_BASE
    return "http://127.0.0.1:9978/proxy"


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


def _load_java_danmu_name():
    try:
        jl = __import__("com.github.catvod.spider.merge.m.l", fromlist=["l"])
        name = jl.b("danmuvodname")
        if name:
            return clean_name(name)
        name = jl.b("searchvodname")
        if name:
            return clean_name(name)
    except Exception:
        pass
    return clean_name(_DANMU_META.get("name", ""))


def _load_java_danmu_index():
    try:
        jl = __import__("com.github.catvod.spider.merge.m.l", fromlist=["l"])
        ep = jl.b("danmuvodindex")
        if ep:
            return str(ep)
    except Exception:
        pass
    return str(_DANMU_META.get("index", "") or "")


def _call_jar_process_vod(vod):
    if not isinstance(vod, dict):
        return
    try:
        import json
        aa = __import__("com.github.catvod.spider.merge.a.a", fromlist=["a"])
        payload = json.dumps({"list": [vod]}, ensure_ascii=False)
        aa.processVodData(payload)
        return
    except Exception:
        pass


def _call_jar_add_danmaku(raw_json):
    for mod_path, cls_name in (
        ("com.github.catvod.spider.merge.a.a", "a"),
        ("com.github.catvod.spider.merge.b.P", "P"),
    ):
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            fn = getattr(mod, "addDanmaku", None)
            if fn:
                out = fn(raw_json)
                if out:
                    return out
        except Exception:
            continue
    return None


def _vod_id_from_play_id(play_id):
    for part in str(play_id or "").split("&"):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        if key in ("vod_d_id", "vod_id", "vodId"):
            return val.strip()
    return ""


def _danmu_cache_file():
    import os
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".danmu_vod.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "baoge", ".danmu_vod.json"),
    ]
    try:
        from android.os import Environment
        ext = Environment.getExternalStorageDirectory().getAbsolutePath()
        candidates.insert(0, os.path.join(ext, "Android", "data", "danmu_vod.json"))
    except Exception:
        pass
    for path in candidates:
        parent = os.path.dirname(path)
        if parent and (os.path.isdir(parent) or path == candidates[0]):
            return path
    return candidates[0]


def _read_vod_cache():
    import os
    try:
        with open(_danmu_cache_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_vod_cache(data):
    import os
    try:
        with open(_danmu_cache_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def cache_vod_name(vod_id, name, spider=None):
    vid = str(vod_id or "").strip()
    title = clean_name(name)
    if not vid or not title:
        return
    _VOD_ID_NAME[vid] = title
    data = _read_vod_cache()
    data[vid] = title
    _write_vod_cache(data)
    _spider_cache_set(spider, f"danmu_vn_{vid}", title)
    _spider_cache_set(spider, "danmu_vod_name", title)


def load_vod_name(vod_id, spider=None):
    vid = str(vod_id or "").strip()
    if vid:
        if vid in _VOD_ID_NAME:
            return clean_name(_VOD_ID_NAME[vid])
        cached = _spider_cache_get(spider, f"danmu_vn_{vid}")
        if cached:
            return clean_name(cached)
        file_name = clean_name(_read_vod_cache().get(vid, ""))
        if file_name:
            return file_name
    return clean_name(_spider_cache_get(spider, "danmu_vod_name"))


def _normalize_danmaku_field(result):
    """兼容旧逻辑；FongMi 官方 DanmakuAdapter 同时支持字符串与数组。"""
    if not isinstance(result, dict):
        return result
    dan = result.get("danmaku")
    if isinstance(dan, str) and dan.strip():
        return result
    if isinstance(dan, list) and dan:
        fixed = []
        for item in dan:
            if isinstance(item, dict) and item.get("url"):
                fixed.append({"name": item.get("name") or "弹幕", "url": item["url"]})
            elif isinstance(item, str) and item.strip():
                fixed.append({"name": "弹幕", "url": item.strip()})
        if fixed:
            result["danmaku"] = fixed
    elif isinstance(result.get("danmu"), str) and result.get("danmu").strip():
        result["danmaku"] = result["danmu"].strip()
    return result


def _apply_danmaku_fields(result, url):
    url = str(url or "").strip()
    if not url:
        return result
    # 与 JAR addDanmaku 一致：字符串 danmaku，FongMi DanmakuAdapter 原生支持
    result["danmaku"] = url
    result["danmu"] = url
    result["click"] = url
    return result


def _danmu_proxy_response(xml_text):
    text = xml_text if isinstance(xml_text, str) else (xml_text or empty_xml())
    if isinstance(text, str):
        body = text.encode("utf-8")
    else:
        body = text
    try:
        from java.io import ByteArrayInputStream
        return [200, "application/xml", ByteArrayInputStream(body)]
    except Exception:
        return [200, "application/xml", text if isinstance(text, str) else body]


def _attach_danmaku_url(result, vod_name, vod_index="", spider=None, play_id=""):
    try:
        if not isinstance(result, dict):
            return result
        name = clean_name(vod_name)
        if not name:
            return result
        ep = str(vod_index or "").strip() or str(parse_episode(vod_index or name))
        _save_danmu_meta(name, ep)
        url = load_danmu_url(play_id, spider) or build_danmu_url(spider, name, ep, play_id=play_id)
        try:
            jar_raw = _call_jar_add_danmaku(json.dumps(result, ensure_ascii=False))
            if jar_raw:
                jar_obj = json.loads(jar_raw)
                jdan = jar_obj.get("danmaku")
                if isinstance(jdan, str) and jdan.strip():
                    url = jdan.strip()
                elif isinstance(jdan, list) and jdan:
                    first = jdan[0]
                    if isinstance(first, dict) and first.get("url"):
                        url = first["url"]
                    elif isinstance(first, str) and first.strip():
                        url = first.strip()
        except Exception:
            pass
        return _apply_danmaku_fields(result, url)
    except Exception:
        return result


def jar_add_danmaku_to_result(result, vod_name="", episode="", spider=None, play_id="", flag=""):
    """FongMi/OK影视：danmaku 字符串 + click，与 JAR 源一致。"""
    try:
        if not isinstance(result, dict):
            return result
        name = clean_name(vod_name) or resolve_danmu_name(spider, play_id, flag)
        ep = resolve_danmu_episode(spider, play_id, flag, episode)
        if not name:
            return result
        return _attach_danmaku_url(result, name, ep, spider=spider, play_id=play_id)
    except Exception:
        return result


def attach_danmaku(spider, result, vod_name, vod_index="", play_id=""):
    return jar_add_danmaku_to_result(result, vod_name, vod_index, spider=spider, play_id=play_id)


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


def build_py_danmu_url(spider, vod_name, vod_index=""):
    """Python 源：走 getProxyUrl + type=danmu，由 localProxy 返回 XML。"""
    base = _resolve_spider_proxy(spider)
    if not base:
        return ""
    name = _url_param(clean_name(vod_name))
    ep = _url_param(vod_index or "")
    return _proxy_append(base, f"type=danmu&vodName={name}&vodIndex={ep}")


def build_appdanmu_url(spider, vod_name, vod_index=""):
    return build_danmu_url(spider, vod_name, vod_index)


def _build_proxy_danmu_url(spider, name, ep):
    nv = _url_param(clean_name(name))
    ev = _url_param(ep or "")
    py = _resolve_spider_proxy(spider)
    if py:
        return _proxy_append(py, f"type=appdanmu&vodName={nv}&vodIndex={ev}")
    try:
        proxy = __import__("com.github.catvod.spider.Proxy", fromlist=["Proxy"])
        jar_url = str(proxy.getUrl() or "").strip()
        if jar_url:
            return _proxy_append(jar_url, f"do=appdanmu&vodName={nv}&vodIndex={ev}")
    except Exception:
        pass
    base = _jar_proxy_base(spider)
    return f"{base}?do=appdanmu&vodName={nv}&vodIndex={ev}"


def build_danmu_url(spider, vod_name, vod_index="", api_base=DEFAULT_DANMU_API, play_id=""):
    """播放时只用缓存/本地代理，避免 30s 超时内拉 360 链接。"""
    name = clean_name(vod_name)
    if not name:
        return ""
    ep = str(vod_index or "").strip() or str(parse_episode(vod_index or name))
    cached = load_danmu_url(play_id, spider) if play_id else ""
    if cached:
        return cached
    return _build_proxy_danmu_url(spider, name, ep)


def _precache_direct_danmu(spider, vod_name, play_url):
    title = clean_name(vod_name)
    if not title or not play_url:
        return
    for block in str(play_url).split("$$$"):
        for item in block.split("#"):
            item = item.strip()
            if not item or "$" not in item:
                continue
            ep, key = item.split("$", 1)
            key = key.strip()
            ep = ep.strip()
            if not key:
                continue
            try:
                direct = build_direct_player_danmu_url(title, ep)
                if direct:
                    _cache_danmu_url(key, direct, spider)
                    break
            except Exception:
                pass
        if _DANMU_URL_BY_KEY:
            break


def init_spider_cache(spider):
    if not hasattr(spider, "_vod_name"):
        spider._vod_name = ""
    if not hasattr(spider, "_ep_map"):
        spider._ep_map = {}


def remember_playlist(spider, vod_name="", play_url=""):
    init_spider_cache(spider)
    title = clean_name(vod_name)
    if title:
        spider._vod_name = title
        _spider_cache_set(spider, "danmu_vod_name", title)
        _spider_cache_set(spider, "current_vod_name", title)
    spider._ep_map = {}
    _cache_play_meta(vod_name, play_url, spider)
    if not play_url:
        return
    for block in str(play_url).split("$$$"):
        for item in block.split("#"):
            item = item.strip()
            if not item or "$" not in item:
                continue
            ep, key = item.split("$", 1)
            key = key.strip()
            ep = ep.strip()
            spider._ep_map[key] = ep
            _cache_ep_by_key(key, ep, spider)
    try:
        _precache_direct_danmu(spider, title, play_url)
    except Exception:
        pass


def remember_from_vod(spider, vod):
    try:
        if isinstance(vod, dict):
            name = vod.get("vod_name", "")
            vid = vod.get("vod_id", "")
            remember_playlist(spider, name, vod.get("vod_play_url", ""))
            cache_vod_name(vid, name, spider)
            if vid:
                _spider_cache_set(spider, "current_vod_id", str(vid))
            _save_danmu_meta(name, "")
            _call_jar_process_vod(vod)
    except Exception:
        pass


def attach_player(spider, result, play_id, flag="", vod_name="", ep_name=""):
    try:
        init_spider_cache(spider)
        return jar_add_danmaku_to_result(
            result,
            vod_name or getattr(spider, "_vod_name", ""),
            ep_name,
            spider=spider,
            play_id=play_id,
            flag=flag,
        )
    except Exception:
        return result


def finalize_player(spider, result, play_id="", flag="", vod_name="", ep_name=""):
    return attach_player(spider, result, play_id, flag, vod_name, ep_name)


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
        or _load_java_danmu_name()
        or _DANMU_META.get("name")
        or ""
    )
    if not name:
        vid = _vod_id_from_play_id(params.get("vod_d_id") or params.get("vod_id") or "")
        name = load_vod_name(vid)
    ep = (
        params.get("vodIndex")
        or params.get("vodindex")
        or params.get("index")
        or _load_java_danmu_index()
        or _DANMU_META.get("index")
        or ""
    )
    xml = _jar_appdanmu_xml(name, ep)
    if xml is None:
        xml = _fetch_appdanmu_via_jar_http(name, ep)
    if not xml or "<d " not in xml:
        xml, _source = fetch_danmu_xml(name, ep, api_base=api_base)
    return _danmu_proxy_response(xml or empty_xml())


def proxy_with_danmu(params, fallback=None, api_base=DEFAULT_DANMU_API):
    hit = handle_danmu_proxy(params, api_base=api_base)
    if hit:
        return hit
    return fallback(params) if fallback else None
