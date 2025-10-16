#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""订单查询和基础服务模块"""

import json
import time
import re
from datetime import datetime
import urllib.parse
from utils import get_logger


class OrderQueryService:
    """订单查询服务"""
    
    def __init__(self, session=None, logger=None):
        """
        初始化订单查询服务
        
        Args:
            session: requests会话对象
            logger: 日志记录器
        """
        self.session = session
        self.logger = logger or get_logger('12306')

    def get_repeat_submit_token(self, last_leftticket_init_url=None):
        """获取REPEAT_SUBMIT_TOKEN"""
        try:
            self.logger.info("获取REPEAT_SUBMIT_TOKEN...")

            # 添加_uab_collina cookie（阿里云bot管理cookie）
            if '_uab_collina' not in self.session.cookies:
                collina_value = f"{int(time.time() * 1000)}{str(int(time.time() * 10000000))[-14:]}"
                self.session.cookies.set('_uab_collina', collina_value, domain='kyfw.12306.cn')
                self.logger.info(f"添加_uab_collina cookie: {collina_value}")

            # 第二步：访问确认乘客页面获取token
            url = "https://kyfw.12306.cn/otn/confirmPassenger/initDc"

            referer = last_leftticket_init_url or 'https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc'
            headers = {
                'Referer': referer,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'max-age=0',
                'Origin': 'https://kyfw.12306.cn',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Upgrade-Insecure-Requests': '1'
            }
            self.logger.info(f"initDc Referer: {referer}")

            data = {'_json_att': ''}

            time.sleep(1)

            self.logger.info("访问确认乘客页面(POST initDc)...")
            response = self.session.post(url, data=data, headers=headers, timeout=30)

            if response.status_code == 200:
                content = response.text

                # 保存响应内容用于调试
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'confirm_passenger_{timestamp}.html'
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.info(f"确认乘客页面已保存到 {filename}")

                # 检查系统繁忙
                if '系统忙' in content or '系统繁忙' in content:
                    self.logger.warning("12306系统繁忙")
                    return None

                # 检查是否被重定向到登录页面
                if ('请登录' in content or
                    '<title>登录' in content or
                    'otn/resources/login.html' in response.url or
                    response.url.endswith('login.html')):
                    self.logger.error("访问确认乘客页面被重定向到登录页面")
                    return None

                # 尝试多种token提取模式
                patterns = [
                    r"globalRepeatSubmitToken\s*=\s*['\"]([^'\"]+)['\"]",
                    r"REPEAT_SUBMIT_TOKEN\s*=\s*['\"]([^'\"]+)['\"]",
                    r"repeatSubmitToken\s*=\s*['\"]([^'\"]+)['\"]",
                ]

                for pattern in patterns:
                    token_match = re.search(pattern, content, re.IGNORECASE)
                    if token_match:
                        token = token_match.group(1)
                        if len(token) > 10:
                            self.logger.info(f"获取到REPEAT_SUBMIT_TOKEN: {token}")
                            return token

                if 'globalRepeatSubmitToken = null' in content:
                    self.logger.warning("token为null，需要先提交订单请求")
                    return "NEED_SUBMIT_ORDER_FIRST"

                if '<title>' in content and '确认乘客' in content:
                    self.logger.warning("页面加载正常但未找到token")
                    return "NEED_SUBMIT_ORDER_FIRST"
                else:
                    self.logger.error("确认乘客页面加载异常")
                    return None

            else:
                self.logger.error(f"获取token页面HTTP错误: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"获取REPEAT_SUBMIT_TOKEN异常: {e}")
            return None

    def get_passengers(self, repeat_submit_token):
        """获取乘客信息"""
        try:
            url = "https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs"

            data = {
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': repeat_submit_token or ''
            }

            self.logger.info("获取乘客信息...")
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info("成功获取乘客信息")

                if result.get('status'):
                    passengers = result.get('data', {}).get('normal_passengers', [])
                    if passengers:
                        self.logger.info(f"找到 {len(passengers)} 位乘客")
                        return True, passengers
                    else:
                        self.logger.warning("没有找到乘客信息")
                        return False, None
                else:
                    self.logger.error(f"获取乘客信息失败: {result}")
                    return False, None
            else:
                self.logger.error(f"getPassengerDTOs HTTP错误: {response.status_code}")
                return False, None

        except Exception as e:
            self.logger.error(f"获取乘客信息异常: {e}")
            return False, None

    def get_queue_count(self, train_info, seat_type_code, from_station, to_station, 
                        train_date, repeat_submit_token):
        """获取排队人数"""
        try:
            url = "https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount"

            from datetime import datetime
            train_date_obj = datetime.strptime(train_date, '%Y-%m-%d')
            weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            train_date_str = f"{weekdays[train_date_obj.weekday()]} {months[train_date_obj.month-1]} {train_date_obj.day:02d} {train_date_obj.year} 00:00:00 GMT+0800 (中国标准时间)"

            data = {
                'train_date': train_date_str,
                'train_no': train_info.get('train_no', ''),
                'stationTrainCode': train_info.get('列车号', ''),
                'seatType': seat_type_code,
                'fromStationTelecode': from_station,
                'toStationTelecode': to_station,
                'leftTicket': train_info.get('leftTicket', ''),
                'purpose_codes': '00',
                'train_location': train_info.get('train_location', ''),
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': repeat_submit_token or ''
            }

            self.logger.info("获取排队人数...")
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"getQueueCount响应: {result}")

                if result.get('status'):
                    return True, result
                else:
                    self.logger.error(f"获取排队人数失败: {result}")
                    return False, result
            else:
                self.logger.error(f"getQueueCount HTTP错误: {response.status_code}")
                return False, None

        except Exception as e:
            self.logger.error(f"获取排队人数异常: {e}")
            return False, None

    def query_order_wait_time(self, repeat_submit_token):
        """查询订单等待时间"""
        try:
            url = "https://kyfw.12306.cn/otn/confirmPassenger/queryOrderWaitTime"

            params = {
                'random': str(int(time.time() * 1000)),
                'tourFlag': 'dc',
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': repeat_submit_token or ''
            }

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                try:
                    result = response.json()
                    self.logger.info(f"轮询响应: {result}")

                    if result.get('status'):
                        data = result.get('data', {})
                        wait_time = data.get('waitTime', -1)
                        wait_count = data.get('waitCount', 0)

                        self.logger.info(f"waitTime={wait_time}, waitCount={wait_count}")

                        if wait_time == -4:
                            self.logger.error("检测到异常排队状态！waitTime=-4")
                            return 'failed', data
                        elif wait_time == -3:
                            self.logger.error("订单提交被系统拒绝 (waitTime=-3)")
                            return 'failed', data
                        elif wait_time == -1:
                            self.logger.info("订单处理完成")
                            return 'completed', data
                        elif wait_time == -2:
                            self.logger.warning("订单失败")
                            return 'failed', data
                        elif wait_time == -100:
                            self.logger.info(f"订单异步处理中... waitTime=-100")
                            return 'waiting', data
                        elif wait_time > 0:
                            self.logger.info(f"排队中... 等待时间: {wait_time}秒")
                            return 'waiting', data
                        else:
                            self.logger.warning(f"未知的waitTime值: {wait_time}")
                            return 'waiting', data
                    else:
                        self.logger.error(f"查询等待时间失败: {result}")
                        return 'error', result

                except json.JSONDecodeError as e:
                    self.logger.error(f"解析等待时间响应失败: {e}")
                    return 'error', None
            else:
                self.logger.error(f"查询等待时间HTTP错误: {response.status_code}")
                return 'error', None

        except Exception as e:
            self.logger.error(f"查询等待时间异常: {e}")
            return 'error', None

    def get_order_result(self, order_id, repeat_submit_token):
        """获取订单最终结果"""
        try:
            url = "https://kyfw.12306.cn/otn/confirmPassenger/resultOrderForDcQueue"

            data = {
                'orderSequence_no': order_id,
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': repeat_submit_token or ''
            }

            self.logger.info(f"获取订单结果，订单号: {order_id}")
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                try:
                    result = response.json()
                    self.logger.info(f"订单结果响应: {result}")

                    if result.get('status') and result.get('data', {}).get('submitStatus'):
                        return result
                    else:
                        self.logger.warning(f"订单提交状态: {result}")
                        return None

                except json.JSONDecodeError as e:
                    self.logger.error(f"解析订单结果失败: {e}")
                    return None
            else:
                self.logger.error(f"获取订单结果HTTP错误: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"获取订单结果异常: {e}")
            return None
