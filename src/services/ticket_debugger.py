#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""车票查询服务模块"""

import json
import requests
import urllib.parse
from datetime import datetime
import time
import re
import logging


class TrainTicketDebugger:
    """12306火车票查询调试器"""
    
    def __init__(self, config=None, session=None, station_mapping=None, logger=None):
        """
        初始化调试器
        
        Args:
            config: API配置字典
            session: requests会话对象
            station_mapping: 车站代码映射
            logger: 日志记录器
        """
        self.config = config or {}
        self.base_url = self.config.get('base_url', 'https://kyfw.12306.cn/otn/leftTicket/query')
        self.headers = self.config.get('headers', {})
        self.query_params = self.config.get('query_params', {})
        self.station_mapping = station_mapping or {}
        
        # 使用传入的session或创建新的
        self.session = session if session is not None else requests.Session()
        self.session.headers.update(self.headers)

        # 使用传入的logger或创建新的
        self.logger = logger or logging.getLogger(__name__)

    def visit_homepage(self):
        """访问12306首页获取cookies"""
        try:
            self.logger.info("正在访问12306首页获取cookies...")
            homepage_url = "https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc"

            response = self.session.get(homepage_url, timeout=30)
            self.logger.info(f"首页访问状态码: {response.status_code}")
            self.logger.info(f"获取到的cookies: {dict(self.session.cookies)}")

            # 缩短等待时间
            time.sleep(0.5)

            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"访问首页失败: {e}")
            return False

    def make_request(self):
        """发送API请求"""
        try:
            # 先访问首页获取cookies
            if not self.visit_homepage():
                self.logger.warning("访问首页失败，继续尝试直接请求API...")

            self.logger.info(f"请求URL: {self.base_url}")
            self.logger.info(f"请求参数: {self.query_params}")

            # 构建完整URL
            full_url = f"{self.base_url}?{urllib.parse.urlencode(self.query_params)}"
            self.logger.info(f"完整URL: {full_url}")

            response = self.session.get(
                self.base_url,
                params=self.query_params,
                timeout=30,
                allow_redirects=True
            )

            self.logger.info(f"响应状态码: {response.status_code}")
            self.logger.info(f"响应Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            self.logger.info(f"响应大小: {len(response.content)} bytes")

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')

                # 检查是否返回JSON
                if 'application/json' in content_type or 'text/json' in content_type:
                    try:
                        json_data = response.json()
                        self.logger.info("成功获取JSON响应")
                        return json_data
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON解析失败: {e}")
                        self._debug_response_content(response)
                        return None
                else:
                    self.logger.warning(f"返回的不是JSON格式，Content-Type: {content_type}")
                    self.logger.warning("可能被重定向到登录页面或被反爬虫拦截")
                    self._debug_response_content(response)
                    return None
            else:
                self.logger.error(f"请求失败: {response.status_code}")
                self.logger.error(f"响应内容: {response.text[:500]}...")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求异常: {e}")
            return None

    def _debug_response_content(self, response):
        """调试响应内容"""
        content = response.text
        self.logger.info("响应内容分析:")
        self.logger.info(f"- 内容长度: {len(content)} 字符")

        # 检查是否包含常见的12306页面元素
        if '<title>' in content:
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                self.logger.info(f"- 页面标题: {title_match.group(1)}")

        if '登录' in content or 'login' in content.lower():
            self.logger.warning("- 检测到登录相关内容，可能需要登录")

        if '验证码' in content or 'captcha' in content.lower():
            self.logger.warning("- 检测到验证码相关内容")

        if 'script' in content.lower():
            self.logger.info("- 检测到JavaScript代码，这是HTML页面")

        # 保存响应内容到文件以便分析
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'response_debug_{timestamp}.html'
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        self.logger.info(f"- 完整响应已保存到 {filename}")

        # 记录前500字符到日志
        self.logger.debug(f"响应内容前500字符: {content[:500]}")
        if len(content) > 500:
            self.logger.debug("...")

    def decode_train_info(self, encoded_string):
        """解码火车信息字符串"""
        try:
            decoded = urllib.parse.unquote(encoded_string)
            parts = decoded.split('|')

            if len(parts) >= 35:
                train_info = {
                    '列车号': parts[3],
                    '出发站代码': parts[6],
                    '到达站代码': parts[7],
                    '出发时间': parts[8],
                    '到达时间': parts[9],
                    '历时': parts[10],
                    '出发站': self.station_mapping.get(parts[6], parts[6]),
                    '到达站': self.station_mapping.get(parts[7], parts[7]),
                    '日期': parts[13],
                    '商务座': parts[32].split('#')[0] if '#' in parts[32] else parts[32],
                    '一等座': parts[31].split('#')[0] if '#' in parts[31] else parts[31],
                    '二等座': parts[30].split('#')[0] if '#' in parts[30] else parts[30],
                    '硬卧': parts[28].split('#')[0] if '#' in parts[28] else parts[28],
                    '软卧': parts[23].split('#')[0] if '#' in parts[23] else parts[23],
                    '硬座': parts[29].split('#')[0] if '#' in parts[29] else parts[29],
                    '无座': parts[26].split('#')[0] if '#' in parts[26] else parts[26],
                    # 添加订单提交需要的字段
                    'train_no': parts[2],  # 车次编号
                    'leftTicket': parts[12],  # 剩余票信息
                    'train_location': parts[15] if len(parts) > 15 else '',  # 车次位置信息
                }
                return train_info
            else:
                self.logger.warning(f"数据格式异常，字段数量: {len(parts)}")
                return None

        except Exception as e:
            self.logger.error(f"解码失败: {e}")
            return None

    def parse_response(self, response_data):
        """解析响应数据"""
        if not response_data:
            self.logger.warning("没有响应数据")
            return

        self.logger.info("12306 火车票查询结果")

        if response_data.get('status'):
            data = response_data.get('data', {})
            results = data.get('result', [])

            self.logger.info(f"查询状态: 成功")
            self.logger.info(f"找到 {len(results)} 趟列车")
            self.logger.info(f"站点映射: {data.get('map', {})}")

            for i, result in enumerate(results, 1):
                self.logger.info(f"\n第 {i} 趟列车:")
                train_info = self.decode_train_info(result)

                if train_info:
                    for key, value in train_info.items():
                        if value and value != '无' and value != '':
                            self.logger.info(f"  {key}: {value}")

                    # 同时在控制台显示简要信息
                    seat_status = train_info.get('二等座', '无')
                    if seat_status == '*':
                        seat_status = '未开售'
                    print(f"第{i}趟: {train_info.get('列车号', '')} {train_info.get('出发站', '')}->{train_info.get('到达站', '')} {train_info.get('出发时间', '')}-{train_info.get('到达时间', '')} 二等座:{seat_status}")
                else:
                    self.logger.warning(f"  解码失败，原始数据: {result[:100]}...")

        else:
            self.logger.error(f"查询失败: {response_data.get('messages', '未知错误')}")

    def debug(self):
        """执行调试"""
        self.logger.info("开始调试 12306 API...")
        self.logger.info(f"当前时间: {datetime.now()}")
        print(f"\n正在查询火车票信息...")
        print(f"查询参数: {self.query_params}")

        response_data = self.make_request()
        self.parse_response(response_data)

        return response_data
