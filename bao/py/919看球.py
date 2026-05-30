# -*- coding: utf-8 -*-
"""919体育 — 足球/篮球赛事，API 直链 m3u8，播放稳定。"""
import json

from base.spider import Spider as BaseSpider

DEFAULT_API = "https://01cs01.fusk39cd.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class Spider(BaseSpider):
    def getName(self):
        return "919看球"

    def init(self, extend=""):
        self.api = (extend or DEFAULT_API).strip().rstrip("/") or DEFAULT_API
        self.headers = {"User-Agent": UA}

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1", "type_name": "全部"},
                {"type_id": "2", "type_name": "足球"},
                {"type_id": "3", "type_name": "篮球"},
            ]
        }

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "1").strip() or "1"
        try:
            url = f"{self.api}/api/web/live_lists/{tid}"
            data = json.loads(self.fetch(url, headers=self.headers, timeout=12).text)
            if data.get("code") != 200:
                return {"list": []}
            rows = (data.get("data") or {}).get("data") or []
            items = []
            for row in rows:
                if not row.get("tournament_id"):
                    continue
                vid = f"{row.get('type')}|{row.get('tournament_id')}|{row.get('member_id')}"
                name = f"{row.get('home_team_zh', '')} VS {row.get('away_team_zh', '')}".strip()
                items.append(
                    {
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": row.get("cover") or "",
                        "vod_remarks": row.get("league_name_zh") or "直播",
                    }
                )
            return {
                "list": items,
                "page": int(pg or 1),
                "pagecount": 1,
                "limit": 20,
                "total": len(items),
            }
        except Exception:
            return {"list": []}

    def detailContent(self, array):
        try:
            parts = str(array[0]).split("|")
            if len(parts) != 3:
                return {"list": []}
            typ, tid, mid = parts
            url = f"{self.api}/api/web/live_lists/{typ}/detail/{tid}?member_id={mid}"
            data = json.loads(self.fetch(url, headers=self.headers, timeout=12).text)
            if data.get("code") != 200:
                return {"list": []}
            body = data.get("data") or {}
            detail = body.get("detail") or {}
            more = body.get("more") or []
            name = f"{detail.get('home_team_zh', '')} VS {detail.get('away_team_zh', '')}".strip()
            from_names, from_urls = [], []
            for i, row in enumerate(more):
                user = row.get("username") or f"解说{i + 1}"
                lines = []
                if row.get("screen_url_m3u8"):
                    lines.append(f"线路二${row['screen_url_m3u8']}")
                if row.get("screen_url"):
                    lines.append(f"线路一${row['screen_url']}")
                if lines:
                    from_names.append(user)
                    from_urls.append("#".join(lines))
            return {
                "list": [
                    {
                        "vod_id": array[0],
                        "vod_name": name,
                        "vod_pic": detail.get("cover") or "",
                        "vod_content": detail.get("room_notice") or "",
                        "vod_play_from": "$$$".join(from_names) or "919看球",
                        "vod_play_url": "$$$".join(from_urls),
                    }
                ]
            }
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        key = (key or "").strip().lower()
        if not key:
            return {"list": []}
        out = []
        for tid in ("1", "2", "3"):
            block = self.categoryContent(tid, "1", False, {})
            for vod in block.get("list") or []:
                text = f"{vod.get('vod_name', '')} {vod.get('vod_remarks', '')}".lower()
                if key in text:
                    out.append(vod)
        return {"list": out}

    def playerContent(self, flag, id, vipFlags):
        url = (id or "").strip()
        return {"parse": 0, "url": url, "header": dict(self.headers)}
