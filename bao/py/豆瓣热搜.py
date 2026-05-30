# coding=utf-8
"""豆瓣实时热搜 — 供搜索页「热搜」与首页推荐，每次请求拉最新数据。"""
import json
import re
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    HOT_URL = (
        "https://frodo.douban.com/api/v2/subject_collection/"
        "subject_real_time_hotest/items?apikey=0ac44ae016490db2204ce0a042db2916"
    )
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36 "
            "MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat"
        ),
        "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/84/page-frame.html",
        "Host": "frodo.douban.com",
    }

    def getName(self):
        return "豆瓣热搜"

    def init(self, extend=""):
        pass

    def _fetch_hot(self):
        try:
            rsp = self.fetch(self.HOT_URL, headers=self.HEADERS, timeout=12)
            data = json.loads(rsp.text)
            items = data.get("subject_collection_items") or []
            out = []
            for i, item in enumerate(items):
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                pic = ""
                try:
                    pic = item.get("pic", {}).get("normal") or ""
                except Exception:
                    pass
                remark = ""
                try:
                    remark = str(item.get("rating", {}).get("value") or "")
                    if remark:
                        remark = "评分：" + remark
                except Exception:
                    pass
                out.append({
                    "vod_id": "msearch:" + str(item.get("id", i)),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            return out
        except Exception:
            return []

    def homeContent(self, filter):
        hot = self._fetch_hot()
        return {
            "class": [{"type_id": "hot", "type_name": "豆瓣热搜"}],
            "list": hot,
        }

    def homeVideoContent(self):
        return {"list": self._fetch_hot()}

    def categoryContent(self, tid, pg, filter, extend):
        return {"list": self._fetch_hot()}

    def detailContent(self, array):
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        return {}
