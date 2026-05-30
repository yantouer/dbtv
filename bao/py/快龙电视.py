# -*- coding: utf-8 -*-
"""快龙电视(kltvv) — 央视/卫视 + 体育直播（宝哥影视同源）。"""
import base64
import json
import re
from urllib.parse import quote, unquote

from base.spider import Spider as BaseSpider

DEFAULT_BASES = (
    "http://tv.kltvv.com",
    "http://tv.kltvyg.top",
    "http://43.129.218.15:6666",
)
DEFAULT_SPORT_BASE = "http://129.211.6.182:8855/1/"
TV_RC4_KEY = "237296kltvv"
SP_RC4_KEY = "Gmf9LAAeTVdqKelS"
UA = (
    "Mozilla/5.0 (Linux; Android 11; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


def _rc4_hex(data: bytes, key: str) -> bytes:
    s_box = list(range(256))
    j = 0
    key_b = key.encode("utf-8")
    for i in range(256):
        j = (j + s_box[i] + key_b[i % len(key_b)]) % 256
        s_box[i], s_box[j] = s_box[j], s_box[i]
    i = j = 0
    out = bytearray()
    for b in data:
        i = (i + 1) % 256
        j = (j + s_box[i]) % 256
        s_box[i], s_box[j] = s_box[j], s_box[i]
        out.append(b ^ s_box[(s_box[i] + s_box[j]) % 256])
    return bytes(out)


def _decrypt_hex(cipher_hex: str, key: str) -> str:
    raw = _rc4_hex(bytes.fromhex(cipher_hex), key).decode("utf-8", "replace")
    return raw.replace("dz#", "").replace("#&&&&mz##", "").strip()


def _b64enc(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _b64dec(text: str) -> str:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad).decode("utf-8")


def _split_kltvv(text: str):
    return [x for x in re.split(r"#kltv#", text or "") if x.strip()]


def _kltvv_fields(block: str):
    out = {}
    for key in ("mz", "id", "sj", "dz", "au", "lts"):
        m = re.search(rf"{key}#([^#]*)", block)
        if m:
            out[key] = m.group(1)
    return out


def _parse_tv_regions(text: str):
    parts = [p.strip() for p in (text or "").split("#") if p.strip()]
    items = []
    i = 0
    while i < len(parts):
        if parts[i] == "id" and i + 1 < len(parts):
            name = parts[i - 1] if i >= 1 else parts[i + 1]
            items.append((name, parts[i + 1]))
            i += 2
        else:
            i += 1
    return items


def _parse_tv_lines(text: str):
    items = []
    seen = set()
    for m in re.finditer(r"#\s*(\d+)\s*#id#([^#]+)", text or ""):
        name = f"线路{m.group(1)}"
        lid = m.group(2).replace("=&&", "")
        if lid in seen:
            continue
        seen.add(lid)
        items.append((name, lid))
    return items


def _parse_sport_lines(text: str):
    items = []
    seen = set()
    for blk in _split_kltvv(text):
        f = _kltvv_fields(blk)
        dz = f.get("dz")
        if not dz:
            continue
        name = f.get("id") or f.get("mz") or f"线路{len(items) + 1}"
        if dz in seen:
            continue
        seen.add(dz)
        items.append((name, dz))
    return items


class Spider(BaseSpider):
    def getName(self):
        return "快龙电视"

    def init(self, extend=""):
        ext = (extend or "").strip()
        if ext:
            self.bases = [b.strip().rstrip("/") for b in ext.split(",") if b.strip()]
        else:
            self.bases = list(DEFAULT_BASES)
        self.base = self.bases[0]
        self.headers = {"User-Agent": UA}
        self.sport_base = DEFAULT_SPORT_BASE.rstrip("/") + "/"
        self._sport_ready = False

    def _ensure_sport_base(self):
        if self._sport_ready:
            return
        for base in self.bases:
            try:
                cfg = self.fetch(
                    f"{base.rstrip('/')}/api/api.php?bb=9.9",
                    headers=self.headers,
                    timeout=12,
                ).text
                m = re.search(r"url2#([^#]+)#", cfg)
                if m and m.group(1).startswith("http"):
                    self.sport_base = m.group(1).rstrip("/") + "/"
                    break
            except Exception:
                pass
        self._sport_ready = True

    def _fetch_tv(self, path: str) -> str:
        last_err = None
        for base in self.bases:
            url = f"{base.rstrip('/')}/tvb/dstv/{path.lstrip('/')}"
            try:
                resp = self.fetch(url, headers=self.headers, timeout=12)
                if resp.status_code == 200 and resp.text:
                    self.base = base.rstrip("/")
                    return resp.text
            except Exception as exc:
                last_err = exc
        if last_err:
            raise last_err
        return ""

    def _fetch_sport(self, path: str) -> str:
        self._ensure_sport_base()
        url = f"{self.sport_base.rstrip('/')}/{path.lstrip('/')}"
        resp = self.fetch(url, headers=self.headers, timeout=12)
        if resp.status_code == 200:
            return resp.text
        return ""

    @staticmethod
    def _tid_decode(tid: str):
        tid = unquote(str(tid or "").strip())
        for prefix, kind in (
            ("tvch:", "tvch"),
            ("spm:", "spm"),
            ("tv:", "tv"),
            ("sp:", "sp"),
        ):
            if tid.startswith(prefix):
                return kind, tid[len(prefix) :]
        return "tv", tid

    @staticmethod
    def _make_tid(kind: str, raw_id: str) -> str:
        return quote(f"{kind}:{raw_id}", safe="")

    @staticmethod
    def _is_tv_tail(name: str) -> bool:
        return any(k in name for k in ("轮播", "地方"))

    def _sort_home_classes(self, tv_items, sport_items):
        """央视 → 卫视 → 体育 → 各省 → 轮播/地方台。"""
        head, weishi, middle, tail = [], [], [], []
        for name, cid in tv_items:
            item = {"type_id": self._make_tid("tv", cid), "type_name": f"[电视]{name}"}
            if name in ("央视", "中央") or name.startswith("央视"):
                head.append(item)
            elif "卫视" in name:
                weishi.append(item)
            elif self._is_tv_tail(name):
                tail.append(item)
            else:
                middle.append(item)
        ordered = head + weishi + sport_items + middle + tail
        return ordered

    def homeContent(self, filter):
        tv_items = []
        sport_items = []
        try:
            raw = self._fetch_tv("tv1.php")
            tv_items = _parse_tv_regions(raw)
        except Exception:
            pass
        try:
            self._ensure_sport_base()
            raw = self._fetch_sport("zc/vid.php?vid=1")
            for blk in _split_kltvv(raw):
                f = _kltvv_fields(blk)
                if f.get("mz") and f.get("id"):
                    sport_items.append(
                        {
                            "type_id": self._make_tid("sp", f["id"]),
                            "type_name": f"[体育]{f['mz']}",
                        }
                    )
        except Exception:
            pass
        classes = self._sort_home_classes(tv_items, sport_items)
        return {"class": classes or [{"type_id": self._make_tid("tv", "root"), "type_name": "电视直播"}]}

    def categoryContent(self, tid, pg, filter, extend):
        kind, cid = self._tid_decode(tid)
        if kind == "sp":
            return self._sport_matches(cid, pg)
        return self._tv_channels(cid, pg)

    def _tv_channels(self, tid, pg):
        if not tid or tid == "root":
            try:
                raw = self._fetch_tv("tv1.php")
                first = _parse_tv_regions(raw)
                tid = first[0][1] if first else ""
            except Exception:
                return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}
        try:
            raw = self._fetch_tv(f"tv1.php?u={tid}")
            items = []
            for name, ch_id in _parse_tv_regions(raw):
                items.append(
                    {
                        "vod_id": self._make_tid("tvch", ch_id),
                        "vod_name": name,
                        "vod_pic": "",
                        "vod_remarks": "直播",
                    }
                )
            return {
                "list": items,
                "page": int(pg or 1),
                "pagecount": 1,
                "limit": 90,
                "total": len(items),
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    def _sport_matches(self, cat_id, pg):
        try:
            raw = self._fetch_sport(f"zc/api.php?vid=1&id={cat_id}")
            items = []
            for blk in _split_kltvv(raw):
                f = _kltvv_fields(blk)
                if not f.get("mz") or not f.get("id"):
                    continue
                remark = (f.get("sj") or "赛事").split("-")[-1]
                items.append(
                    {
                        "vod_id": self._make_tid("spm", f["id"]),
                        "vod_name": f["mz"],
                        "vod_pic": "",
                        "vod_remarks": remark,
                    }
                )
            return {
                "list": items,
                "page": int(pg or 1),
                "pagecount": 1,
                "limit": 90,
                "total": len(items),
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    def detailContent(self, array):
        kind, cid = self._tid_decode(array[0])
        if kind == "spm":
            return self._sport_detail(cid)
        if kind == "tvch":
            return self._tv_detail(cid)
        return {"list": []}

    def _tv_detail(self, cid):
        try:
            raw = self._fetch_tv(f"tvid1.php?u={cid}")
            lines = _parse_tv_lines(raw)
            if not lines:
                return {"list": []}
            name = ""
            m = re.search(r"mz=([^&]+)", cid)
            if m:
                name = m.group(1)
            play_urls = []
            for line_name, line_id in lines:
                token = _b64enc(json.dumps({"t": "tv", "id": line_id}, ensure_ascii=False))
                play_urls.append(f"{line_name}${token}")
            return {
                "list": [
                    {
                        "vod_id": self._make_tid("tvch", cid),
                        "vod_name": name or "电视直播",
                        "vod_pic": "",
                        "vod_content": "快龙电视 · 多线路",
                        "vod_play_from": "快龙电视",
                        "vod_play_url": "#".join(play_urls),
                    }
                ]
            }
        except Exception:
            return {"list": []}

    def _sport_detail(self, match_id):
        try:
            raw = self._fetch_sport(f"zc/id.php?vid=1&u={match_id}")
            referer = ""
            au_m = re.search(r"au#([^#]+)", raw)
            if au_m:
                au = _decrypt_hex(au_m.group(1), SP_RC4_KEY)
                if au.lower().startswith("referer:"):
                    referer = au.split(":", 1)[1].strip()
            lines = _parse_sport_lines(raw)
            if not lines:
                status = ""
                if "未开" in raw:
                    status = "未开赛"
                elif "完场" in raw:
                    status = "已完场"
                return {
                    "list": [
                        {
                            "vod_id": self._make_tid("spm", match_id),
                            "vod_name": "体育直播",
                            "vod_content": status or "暂无线路",
                            "vod_play_from": "快龙体育",
                            "vod_play_url": "",
                        }
                    ]
                }
            play_urls = []
            for line_name, dz in lines:
                token = _b64enc(
                    json.dumps({"t": "sp", "dz": dz, "ref": referer}, ensure_ascii=False)
                )
                play_urls.append(f"{line_name}${token}")
            name = match_id.split("&")[0]
            for blk in _split_kltvv(raw):
                f = _kltvv_fields(blk)
                if f.get("mz"):
                    name = f["mz"]
                    break
            return {
                "list": [
                    {
                        "vod_id": self._make_tid("spm", match_id),
                        "vod_name": name,
                        "vod_pic": "",
                        "vod_content": "快龙体育 · 多线路",
                        "vod_play_from": "快龙体育",
                        "vod_play_url": "#".join(play_urls),
                    }
                ]
            }
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": []}
        key_up = key.upper()
        out = []
        try:
            raw = self._fetch_tv("tv1.php")
            for _name, region_id in _parse_tv_regions(raw):
                sub = self._fetch_tv(f"tv1.php?u={region_id}")
                for ch_name, ch_id in _parse_tv_regions(sub):
                    if key_up in ch_name.upper() or key in ch_name:
                        out.append(
                            {
                                "vod_id": self._make_tid("tvch", ch_id),
                                "vod_name": ch_name,
                                "vod_pic": "",
                                "vod_remarks": "电视",
                            }
                        )
        except Exception:
            pass
        try:
            self._ensure_sport_base()
            raw = self._fetch_sport("zc/api.php?vid=1&id=1&type=4")
            if not _split_kltvv(raw):
                raw = self._fetch_sport("zc/api.php?vid=1&id=0&type=1")
            for blk in _split_kltvv(raw):
                f = _kltvv_fields(blk)
                if f.get("mz") and f.get("id") and key in f["mz"]:
                    out.append(
                        {
                            "vod_id": self._make_tid("spm", f["id"]),
                            "vod_name": f["mz"],
                            "vod_pic": "",
                            "vod_remarks": (f.get("sj") or "体育").split("-")[-1],
                        }
                    )
        except Exception:
            pass
        return {"list": out}

    def playerContent(self, flag, id, vipFlags):
        try:
            payload = json.loads(_b64dec(unquote((id or "").strip())))
        except Exception:
            return {"parse": 1, "url": "", "header": dict(self.headers)}
        ptype = payload.get("t")
        if ptype == "tv":
            line_id = str(payload.get("id", "")).replace("=&&", "")
            raw = self._fetch_tv(f"tv.php?u={line_id}")
            m = re.search(r"dz&([^&]+)", raw)
            if not m:
                return {"parse": 1, "url": "", "header": dict(self.headers)}
            url = _decrypt_hex(m.group(1), TV_RC4_KEY)
            if not url.startswith("http"):
                return {"parse": 1, "url": "", "header": dict(self.headers)}
            return {"parse": 0, "url": url, "header": dict(self.headers)}
        if ptype == "sp":
            dz = str(payload.get("dz", ""))
            referer = str(payload.get("ref", ""))
            url = _decrypt_hex(dz, SP_RC4_KEY)
            if not url.startswith("http"):
                return {"parse": 1, "url": "", "header": dict(self.headers)}
            header = dict(self.headers)
            if referer:
                header["Referer"] = referer
            return {"parse": 0, "url": url, "header": header}
        return {"parse": 1, "url": "", "header": dict(self.headers)}
