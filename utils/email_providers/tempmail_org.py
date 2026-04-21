from curl_cffi import requests
from typing import Optional, Tuple, List, Dict
from utils import config as cfg

class LinShiYouXiangService:
    BASE_URL = "https://www.linshiyouxiang.net"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.linshiyouxiang.net",
        "Referer": "https://www.linshiyouxiang.net/",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, proxies: Optional[Dict[str, str]] = None):
        self.proxies = proxies
        # 必须使用 chrome 指纹以绕过该站的 Cloudflare 防护
        self.session = requests.Session(impersonate="chrome110")
        self.session.headers.update(self.HEADERS)
        self.session.verify = False
        if self.proxies:
            self.session.proxies.update(self.proxies)
        
        # 核心初始化：模拟真实用户访问首页，获取关键的 mailtt_session Cookie
        try:
            self.session.get(self.BASE_URL, timeout=15)
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] [LinShiYouXiang] 初始化首页失败: {e}")

    def create_email(self) -> Tuple[Optional[str], Optional[str]]:
        """
        适配原代码接口：获取当前分配的邮箱地址
        对应抓包接口：/member/check-login
        """
        try:
            r = self.session.get(f"{self.BASE_URL}/member/check-login", timeout=15)

            if r.status_code == 200:
                data = r.json()
                email = data.get("mail")
                # 该站通过 Cookie 鉴权，为保持原代码 Tuple 返回格式，Token 传 Session 值
                token = self.session.cookies.get("mailtt_session")
                
                if email:
                    return email, token
                else:
                    print(f"[{cfg.ts()}] [ERROR] [LinShiYouXiang] 未在响应中找到邮箱地址: {r.text[:200]}")
            else:
                print(f"[{cfg.ts()}] [ERROR] [LinShiYouXiang] 状态码异常: {r.status_code}")

        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] [LinShiYouXiang] 获取邮箱异常: {e}")

        return None, None

    def get_inbox(self, token: str = None) -> List[dict]:
        """
        适配原代码接口：拉取邮件列表
        对应抓包接口：/get-messages
        """
        try:
            # 该站通常直接使用 get-messages 获取当前会话的邮件
            r = self.session.get(f"{self.BASE_URL}/get-messages", timeout=30)

            if r.status_code == 200:
                data = r.json()
                # 根据该站 API 习惯，直接返回列表或在 messages 键值中
                if isinstance(data, list):
                    return data
                return data.get("messages", [])
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] [LinShiYouXiang] 获取邮件错误: {e}")

        return []

    def get_message_detail(self, message_id: str, domain: str = "gmail") -> str:
        """
        新增方法：获取邮件详情（对应你抓到的 /mail/view 接口）
        用于从邮件正文中提取验证码或点击激活链接
        """
        try:
            # URL 结构参考你抓到的：/mail/view/{id}/{domain}
            url = f"{self.BASE_URL}/mail/view/{message_id}/{domain}"
            r = self.session.get(url, timeout=15)
            
            if r.status_code == 200:
                return r.text  # 返回 HTML 内容
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] [LinShiYouXiang] 读取邮件详情失败: {e}")
        return ""

    def get_domains(self) -> List[str]:
        """
        获取当前可用域名列表（可选，用于全项目关联检查）
        """
        try:
            r = self.session.get(f"{self.BASE_URL}/get-domains", timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return []
