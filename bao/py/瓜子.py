# coding = utf-8
#!/usr/bin/python
import re
import sys
import json
import time
import base64
import hashlib
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from base.spider import Spider

sys.path.append('..')

class Spider(Spider):
    API = 'https://api.w32z7vtd.com'
    TOKEN = (
        '97630f5f85d9f3c639fb7790ca881ef2.4cccf48dc340fe8bded39cfe4ef9ac2adb27425a9069e6cd121210fc7ba518ea8c1cc5629261e94bb6ccb66d8548449c72076c956a2fb46c253008909a6c66347eb458fe3c06d1fcc993ca03a298328f9229f1994a608250c7d1ae124c4520e6e14ce8bf9f4404119a6bbf53cf592a8df2e9145de92ec43ec87cf4bdc563f6e919fe32861b0e93b118ec37d8035fbb3c.'
        '473433979755ccd5ec1b4581ccef76e8209b9e0c6ff819917f12dffad47d0d5e'
    )
    RSA_KEYS = (
        'bMTqITVqBsbq9UjLufsQuBvRiIyfqHLqAWUx0gj0ZUe9DMNDTmJDVZzAh45AZ5LtkC39Y0DU4Ufqm/9gliIJaj7cI/dhmoM5fib5HcslzyGONEwZY5fHBvokBreGaT8bPoaxmnWdTRjRfJzYZV6T06O7GsYVa6DuKTVArb0g48Q='
    )
    AES_KEY = 'U823n8pKnAAbWOST'
    AES_IV = 'wgr8N6BCs7426wf1'
    SIGN_SALT = '*&zvdvdvddbfikkkumtmdwqppp?|4Y!s!2br'
    SUB_DEFAULT = {
        "1": "5",
        "2": "12",
        "3": "30",
        "4": "22",
        "64": "",
    }

    def getName(self):
        return "瓜子"

    def init(self, extend=''):
        self.name = "瓜子"
        self.host = self.API
        self.token = self.TOKEN
        self.header = {
            'Cache-Control': 'no-cache',
            'Version': '2406025',
            'PackageName': 'com.j64f4b21072.ha69699879.dfea0a9826ba.ibf50c9b1d',
            'Ver': '1.9.2',
            'Referer': self.host,
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'okhttp/3.12.0',
        }
        self.cache = {}
        self.cache_timeout = 300
        self._vod_name = ""
        self._ep_map = {}

    VIDEO_UA = (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    )

    def _play_headers(self):
        return {"User-Agent": self.VIDEO_UA, "Referer": self.host + "/"}

    def _parse_param_id(self, id_str):
        body = {}
        for part in (id_str or "").split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                body[k] = v
        return body

    def _norm_extend(self, extend):
        if not extend or extend is True:
            return {}
        if isinstance(extend, str):
            if not extend.strip():
                return {}
            try:
                return json.loads(extend)
            except Exception:
                return {}
        if isinstance(extend, dict):
            return extend
        return {}

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "短剧", "type_id": "64"}
        ]
        
        result['class'] = classes
        
        # 设置筛选条件 - 为所有分类添加筛选
        filters = {}
        for cate in classes:
            tid = cate['type_id']
            filters[tid] = [
                {"key": "area", "name": "地区", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "大陆", "v": "大陆"},
                    {"n": "香港", "v": "香港"},
                    {"n": "台湾", "v": "台湾"},
                    {"n": "美国", "v": "美国"},
                    {"n": "韩国", "v": "韩国"},
                    {"n": "日本", "v": "日本"},
                    {"n": "英国", "v": "英国"},
                    {"n": "法国", "v": "法国"},
                    {"n": "泰国", "v": "泰国"},
                    {"n": "印度", "v": "印度"},
                    {"n": "其他", "v": "其他"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "2022", "v": "2022"},
                    {"n": "2021", "v": "2021"},
                    {"n": "2020", "v": "2020"},
                    {"n": "2019", "v": "2019"},
                    {"n": "2018", "v": "2018"},
                    {"n": "2017", "v": "2017"},
                    {"n": "2016", "v": "2016"},
                    {"n": "2015", "v": "2015"},
                    {"n": "2014", "v": "2014"},
                    {"n": "2013", "v": "2013"},
                    {"n": "2012", "v": "2012"},
                    {"n": "2011", "v": "2011"},
                    {"n": "2010", "v": "2010"},
                    {"n": "2009", "v": "2009"},
                    {"n": "2008", "v": "2008"},
                    {"n": "2007", "v": "2007"},
                    {"n": "2006", "v": "2006"},
                    {"n": "2005", "v": "2005"},
                    {"n": "更早", "v": "2004"}
                ]},
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最新", "v": "d_id"},
                    {"n": "最热", "v": "d_hits"},
                    {"n": "推荐", "v": "d_score"}
                ]}
            ]
        
        result['filters'] = filters
        return result

    def homeVideoContent(self):
        # 首页推荐直接返回空列表，避免加载问题
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        ext = self._norm_extend(extend)
        try:
            body = {
                "tid": tid,
                "page": str(pg),
                "sort": ext.get('sort', 'd_id'),
                "area": ext.get('area', '0'),
                "sub": ext.get('sub', self.SUB_DEFAULT.get(str(tid), '0')),
                "year": ext.get('year', '0'),
                "pageSize": "30",
            }
            
            cache_key = f"category_{tid}_{pg}_{hash(str(body))}"
            data = self.get_cached_data(cache_key, body, '/App/IndexList/indexList')
            
            if data and 'list' in data:
                for item in data['list']:
                    vod_continu = item.get('vod_continu', 0)
                    remarks = '电影' if vod_continu == 0 else f'更新至{vod_continu}集'
                    
                    video = {
                        "vod_id": str(item.get('vod_id', '')),
                        "vod_name": item.get('vod_name', ''),
                        "vod_pic": item.get('vod_pic', ''),
                        "vod_remarks": remarks
                    }
                    videos.append(video)
        except Exception as e:
            print(f"获取分类内容失败: {e}")
        
        return {
            'list': videos,
            'page': int(pg),
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }

    def detailContent(self, ids):
        try:
            vod_id = str(ids[0]).split('/')[0]

            t = str(int(time.time()))
            body1 = {
                "token_id": "1009464",
                "vod_id": vod_id,
                "mobile_time": t,
                "token": self.token,
            }
            qdata = self.get_data(body1, '/App/IndexPlay/playInfo')

            body2 = {
                "vurl_cloud_id": "2",
                "vod_d_id": vod_id,
            }
            jdata = self.get_data(body2, '/App/Resource/Vurl/show')

            if not qdata or 'vodInfo' not in qdata:
                return {'list': []}

            vod = qdata['vodInfo']
            sites = {}

            if jdata and 'list' in jdata:
                for ep in jdata['list']:
                    play = ep.get('play') or {}
                    title = ep.get('title') or '播放'
                    for line, item in play.items():
                        if not isinstance(item, dict):
                            continue
                        if str(item.get('show_type', '')) == '2':
                            continue
                        param = (item.get('param') or '').strip()
                        if not param:
                            continue
                        sites.setdefault(line, []).append(f"{title}${param}")

            video_detail = {
                "vod_id": vod_id,
                "vod_name": vod.get('vod_name', ''),
                "vod_pic": vod.get('vod_pic', ''),
                "vod_year": vod.get('vod_year', ''),
                "vod_area": vod.get('vod_area', ''),
                "vod_actor": vod.get('vod_actor', ''),
                "vod_director": vod.get('vod_director', ''),
                "vod_content": vod.get('vod_use_content', '').strip(),
            }
            if sites:
                ordered = sorted(sites.keys(), key=lambda x: int(x) if str(x).isdigit() else 0, reverse=True)
                video_detail["vod_play_from"] = '$$$'.join(ordered)
                video_detail["vod_play_url"] = '$$$'.join('#'.join(sites[k]) for k in ordered)
                self._vod_name = video_detail.get("vod_name", "")
                self._ep_map = {}
                for eps in sites.values():
                    for item in eps:
                        if "$" in item:
                            title, param = item.split("$", 1)
                            self._ep_map[param] = title
                try:
                    from danmu_util import remember_from_vod
                    remember_from_vod(self, video_detail)
                except Exception:
                    pass

            return {'list': [video_detail]}

        except Exception as e:
            print(f"获取详情失败: {e}")
            return {'list': []}

    def searchContent(self, key, quick, pg=1):
        videos = []
        try:
            body = {
                "keywords": key,
                "order_val": "1",
                "page": str(pg)
            }
            
            # 搜索不使用缓存，确保实时性
            start_time = time.time()
            data = self.get_data(body, '/App/Index/findMoreVod', use_cache=False)
            end_time = time.time()
            
            print(f"搜索请求耗时: {end_time - start_time:.2f}秒")
            
            if data and 'list' in data:
                for item in data['list']:
                    vod_continu = item.get('vod_continu', 0)
                    remarks = '电影' if vod_continu == 0 else f'更新至{vod_continu}集'
                    
                    video = {
                        "vod_id": str(item.get('vod_id', '')),
                        "vod_name": item.get('vod_name', ''),
                        "vod_pic": item.get('vod_pic', ''),
                        "vod_remarks": remarks
                    }
                    videos.append(video)
        except Exception as e:
            print(f"搜索失败: {e}")
        
        return {
            'list': videos,
            'page': int(pg),
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }

    def playerContent(self, flag, id, vipFlags):
        try:
            body = self._parse_param_id(id)
            if not body:
                return {"parse": 0, "jx": 0, "playUrl": "", "url": ""}

            data = self.get_data(body, '/App/Resource/VurlDetail/showOne', use_cache=False)
            url = (data or {}).get('url', '')
            if not url or not self.isVideoFormat(url):
                return {"parse": 0, "jx": 0, "playUrl": "", "url": ""}
            result = {"parse": 0, "jx": 0, "playUrl": "", "url": url}
            try:
                from danmu_util import finalize_player, load_vod_name
                vid = body.get("vod_d_id") or ""
                vn = getattr(self, "_vod_name", "") or load_vod_name(vid, self)
                ep = (
                    self._ep_map.get(id)
                    or self._ep_map.get(str(id))
                    or flag
                )
                finalize_player(self, result, id, flag, vn, ep)
            except Exception:
                pass
            return result
        except Exception as e:
            print(f"播放解析失败: {e}")
            return {"parse": 0, "jx": 0, "playUrl": "", "url": ""}

    def isVideoFormat(self, url):
        if not url:
            return False
        low = url.lower()
        if any(x in low for x in ('.m3u8', '.mp4', '.flv', '.ts', 'decry/vd', '/vd/', 'm3u8')):
            return True
        return any(low.endswith(fmt) for fmt in ('.avi', '.mkv'))

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        try:
            from danmu_util import handle_danmu_proxy
            hit = handle_danmu_proxy(params)
            if hit:
                return hit
        except Exception:
            pass
        try:
            from urllib.parse import urljoin
            raw = params.get('url') or ''
            if not raw:
                return None
            try:
                url = base64.b64decode(raw).decode('utf-8')
            except Exception:
                url = raw
            uas = [
                self.VIDEO_UA,
                "Gz360/1.9.2",
                "Dalvik/2.1.0 (Linux; U; Android 13)",
            ]
            text = ''
            for ua in uas:
                rsp = self.fetch(url, headers={"User-Agent": ua, "Referer": self.host + "/"}, timeout=15)
                text = rsp.text or ''
                if text and not any('xn--' in ln for ln in text.splitlines() if ln.strip() and not ln.startswith('#')):
                    break
            if not text:
                return None
            base = url.rsplit('/', 1)[0] + '/'
            lines = []
            for line in text.splitlines():
                s = line.strip()
                if not s:
                    continue
                if s.startswith('#'):
                    lines.append(s)
                    continue
                if 'xn--' in s:
                    continue
                if not s.startswith('http'):
                    s = urljoin(base, s)
                lines.append(s)
            if not any(not x.startswith('#') for x in lines):
                return None
            return [200, 'application/vnd.apple.mpegurl', '\n'.join(lines) + '\n']
        except Exception as e:
            print(f"localProxy失败: {e}")
            return None

    def aes_encrypt(self, text, key, iv):
        """AES加密"""
        try:
            key_bytes = key.encode('utf-8')
            iv_bytes = iv.encode('utf-8')
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            encrypted = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
            return encrypted.hex().upper()
        except Exception as e:
            print(f"AES加密失败: {e}")
            return ""

    def aes_decrypt(self, text, key, iv):
        """AES解密"""
        try:
            key_bytes = key.encode('utf-8')
            iv_bytes = iv.encode('utf-8')
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            encrypted_bytes = bytes.fromhex(text)
            decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted.decode('utf-8')
        except Exception as e:
            print(f"AES解密失败: {e}")
            return ""

    def rsa_decrypt(self, encrypted_data, private_key):
        """RSA解密"""
        try:
            # 解码base64数据
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # 导入私钥
            rsa_key = RSA.import_key(private_key)
            cipher = PKCS1_v1_5.new(rsa_key)
            
            # 解密
            decrypted = cipher.decrypt(encrypted_bytes, None)
            return decrypted.decode('utf-8') if decrypted else ""
        except Exception as e:
            print(f"RSA解密失败: {e}")
            return ""

    def get_cached_data(self, cache_key, data, path):
        """带缓存的数据获取"""
        current_time = time.time()
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if current_time - timestamp < self.cache_timeout:
                return cached_data
        
        # 缓存不存在或已过期，重新获取
        result = self.get_data(data, path)
        if result:
            self.cache[cache_key] = (result, current_time)
        return result

    def get_data(self, data, path, use_cache=True):
        """获取数据的主要方法"""
        try:
            # 构建缓存键
            cache_key = f"{path}_{hash(str(data))}" if use_cache else None
            
            if use_cache and cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_timeout:
                    return cached_data

            start_time = time.time()
            
            # AES加密请求数据
            request_key = self.aes_encrypt(json.dumps(data), self.AES_KEY, self.AES_IV)
            if not request_key:
                return None
            
            # 生成签名
            t = str(int(time.time()))
            keys = self.RSA_KEYS
            sign_str = f"token_id=,token={self.token},phone_type=1,request_key={request_key},app_id=1,time={t},keys={keys}{self.SIGN_SALT}"
            signature = hashlib.md5(sign_str.encode()).hexdigest().upper()
            
            # 构建请求体
            body = {
                'token': self.token,
                'token_id': '',
                'phone_type': '1',
                'time': t,
                'phone_model': 'xiaomi-2206123sc',
                'keys': keys,
                'request_key': request_key,
                'signature': signature,
                'app_id': '1',
                'ad_version': '1'
            }
            
            # 发送请求 - 设置超时时间
            url = f"{self.host}{path}"
            response = self.post(url, headers=self.header, data=body, timeout=10)
            
            if response.status_code != 200:
                print(f"API请求失败: {response.status_code}, 路径: {path}")
                return None
                
            response_data = response.json()
            if 'data' not in response_data:
                print(f"API返回数据格式错误, 路径: {path}")
                return None
                
            data_response = response_data['data']
            
            # RSA解密响应密钥
            private_key = """-----BEGIN PRIVATE KEY-----
MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGAe6hKrWLi1zQmjTT1
ozbE4QdFeJGNxubxld6GrFGximxfMsMB6BpJhpcTouAqywAFppiKetUBBbXwYsYU
1wNr648XVmPmCMCy4rY8vdliFnbMUj086DU6Z+/oXBdWU3/b1G0DN3E9wULRSwcK
ZT3wj/cCI1vsCm3gj2R5SqkA9Y0CAwEAAQKBgAJH+4CxV0/zBVcLiBCHvSANm0l7
HetybTh/j2p0Y1sTXro4ALwAaCTUeqdBjWiLSo9lNwDHFyq8zX90+gNxa7c5EqcW
V9FmlVXr8VhfBzcZo1nXeNdXFT7tQ2yah/odtdcx+vRMSGJd1t/5k5bDd9wAvYdI
DblMAg+wiKKZ5KcdAkEA1cCakEN4NexkF5tHPRrR6XOY/XHfkqXxEhMqmNbB9U34
saTJnLWIHC8IXys6Qmzz30TtzCjuOqKRRy+FMM4TdwJBAJQZFPjsGC+RqcG5UvVM
iMPhnwe/bXEehShK86yJK/g/UiKrO87h3aEu5gcJqBygTq3BBBoH2md3pr/W+hUM
WBsCQQChfhTIrdDinKi6lRxrdBnn0Ohjg2cwuqK5zzU9p/N+S9x7Ck8wUI53DKm8
jUJE8WAG7WLj/oCOWEh+ic6NIwTdAkEAj0X8nhx6AXsgCYRql1klbqtVmL8+95KZ
K7PnLWG/IfjQUy3pPGoSaZ7fdquG8bq8oyf5+dzjE/oTXcByS+6XRQJAP/5ciy1b
L3NhUhsaOVy55MHXnPjdcTX0FaLi+ybXZIfIQ2P4rb19mVq1feMbCXhz+L1rG8oa
t5lYKfpe8k83ZA==
-----END PRIVATE KEY-----"""
            
            bodyki_json = self.rsa_decrypt(data_response['keys'], private_key)
            if not bodyki_json:
                print("RSA解密失败")
                return None
                
            bodyki = json.loads(bodyki_json)
            
            # AES解密响应数据
            decrypted_data = self.aes_decrypt(data_response['response_key'], bodyki['key'], bodyki['iv'])
            if not decrypted_data:
                print("AES解密失败")
                return None
                
            result = json.loads(decrypted_data)
            
            end_time = time.time()
            print(f"数据获取耗时: {end_time - start_time:.2f}秒, 路径: {path}")
            
            # 缓存结果
            if use_cache and cache_key:
                self.cache[cache_key] = (result, time.time())
                
            return result
            
        except Exception as e:
            print(f"获取数据失败: {e}, 路径: {path}")
            return None

    def get_md5(self, text):
        """计算MD5"""
        return hashlib.md5(text.encode()).hexdigest()

if __name__ == '__main__':
    pass
