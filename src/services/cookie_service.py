#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Cookie管理服务模块"""

import os
import pickle
from src.utils import get_logger


class CookieService:
    """Cookie管理服务"""
    
    def __init__(self, session=None, logger=None):
        """
        初始化Cookie服务
        
        Args:
            session: requests会话对象
            logger: 日志记录器
        """
        self.session = session
        self.logger = logger or get_logger('12306')

    def load_cookies(self, filename='cookies.pkl'):
        """加载cookies"""
        try:
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    cookies = pickle.load(f)
                self.session.cookies.update(cookies)
                self.logger.info(f"从 {filename} 加载cookies成功")

                # 显示加载的关键cookie
                important_cookies = ['JSESSIONID', 'tk', 'uKey', '_jc_save_fromStation']
                loaded_cookies = {k: v for k, v in self.session.cookies.items() if k in important_cookies}
                self.logger.info(f"关键cookies: {loaded_cookies}")

                # 检查是否有必要的认证cookie
                if 'tk' not in self.session.cookies:
                    self.logger.warning("警告: 缺少tk认证cookie，可能需要重新登录")
                    return False

                return True
            else:
                self.logger.warning(f"Cookies文件 {filename} 不存在")
                return False
        except Exception as e:
            self.logger.error(f"加载cookies失败: {e}")
            return False

    def save_cookies(self, filename='cookies.pkl'):
        """保存cookies到文件"""
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.session.cookies, f)
            self.logger.info(f"Cookies已保存到 {filename}")
            return True
        except Exception as e:
            self.logger.error(f"保存cookies失败: {e}")
            return False
