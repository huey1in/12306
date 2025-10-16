#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""订单提交服务模块"""

import json
import time
import re
from datetime import datetime
import urllib.parse
from utils import get_logger, js_escape


class OrderSubmitService:
    """订单提交服务"""
    
    def __init__(self, session=None, logger=None):
        """
        初始化订单提交服务
        
        Args:
            session: requests会话对象
            logger: 日志记录器
        """
        self.session = session
        self.logger = logger or get_logger('12306')
        self.last_leftticket_init_url = None
        self.repeat_submit_token = None
        self.key_check_ischange = None

    def submit_order_request(self, train_info, seat_type, from_station, to_station, 
                            train_date, from_name, to_name):
        """提交订单请求"""
        try:
            self.logger.info(f"提交订单请求: {train_info.get('列车号')} {seat_type}")

            from_name_encoded = urllib.parse.quote(from_name)
            to_name_encoded = urllib.parse.quote(to_name)

            # 构建并访问leftTicket/init页面
            init_url = f"https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc&fs={from_name_encoded},{from_station}&ts={to_name_encoded},{to_station}&date={train_date}&flag=N,N,Y"
            self.last_leftticket_init_url = init_url

            self.logger.info(f"访问leftTicket/init: {init_url}")

            # 保存登录时的JSESSIONID
            original_jsessionid = self.session.cookies.get('JSESSIONID')
            self.logger.info(f"访问前JSESSIONID: {original_jsessionid}")

            # 访问init页面
            init_response = self.session.get(init_url, timeout=30)
            self.logger.info(f"leftTicket/init响应: {init_response.status_code}")

            # 检查JSESSIONID是否被改变
            current_jsessionid = self.session.cookies.get('JSESSIONID')
            if current_jsessionid != original_jsessionid:
                self.logger.warning(f"init页面改变了JSESSIONID")
                self.session.cookies.set('JSESSIONID', original_jsessionid)
                self.logger.info(f"已恢复原始JSESSIONID")

            # 添加_jc_save_*cookies
            self.session.cookies.set('_jc_save_fromStation', js_escape(f'{from_name},{from_station}'))
            self.session.cookies.set('_jc_save_toStation', js_escape(f'{to_name},{to_station}'))
            self.session.cookies.set('_jc_save_fromDate', train_date)
            self.session.cookies.set('_jc_save_toDate', train_date)
            self.session.cookies.set('_jc_save_wfdc_flag', 'dc')
            self.session.cookies.set('_jc_save_showIns', 'true')
            self.session.cookies.set('guidesStatus', 'off')
            self.session.cookies.set('highContrastMode', 'defaltMode')
            self.session.cookies.set('cursorStatus', 'off')
            self.logger.info(f"已设置_jc_save_*cookies")

            # 提交订单
            url = "https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest"

            headers = self.session.headers.copy()
            headers.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://kyfw.12306.cn',
                'Referer': init_url
            })

            secret_str = train_info.get('secretStr', '')
            seat_discount = train_info.get('seat_discount_info', '')

            data = (
                f'secretStr={secret_str}'
                f'&train_date={train_date}'
                f'&back_train_date={train_date}'
                f'&tour_flag=dc'
                f'&purpose_codes=ADULT'
                f'&query_from_station_name={from_name_encoded}'
                f'&query_to_station_name={to_name_encoded}'
                f'&bed_level_info='
                f'&seat_discount_info={seat_discount}'
                f'&undefined'
            )

            self.logger.info(f"提交订单参数: {data[:100]}...")

            response = self.session.post(url, data=data, headers=headers, timeout=30)

            self.logger.info(f"订单提交响应状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    self.logger.info(f"订单提交响应: {result}")

                    if result.get('status'):
                        self.logger.info("订单提交成功，立即访问initDc页面获取token")
                        
                        # 立即访问initDc获取token
                        initdc_url = "https://kyfw.12306.cn/otn/confirmPassenger/initDc"
                        initdc_response = self.session.get(initdc_url, timeout=30)
                        if initdc_response.status_code == 200:
                            self._extract_token_from_initdc(initdc_response.text, train_info)

                        return True, result
                    else:
                        self.logger.error(f"订单提交失败: {result}")
                        return False, result

                except json.JSONDecodeError as e:
                    self.logger.error(f"解析订单响应失败: {e}")
                    return False, None
            else:
                self.logger.error(f"订单提交HTTP错误: {response.status_code}")
                return False, None

        except Exception as e:
            self.logger.error(f"提交订单异常: {e}")
            return False, None

    def _extract_token_from_initdc(self, html_content, train_info):
        """从initDc页面提取token"""
        # 提取REPEAT_SUBMIT_TOKEN
        token_match = re.search(r"globalRepeatSubmitToken\s*=\s*['\"]([^'\"]+)['\"]", html_content)
        if token_match:
            self.repeat_submit_token = token_match.group(1)
            self.logger.info(f"从initDc页面获取到token: {self.repeat_submit_token}")

        # 提取key_check_isChange
        key_check_patterns = [
            r"'key_check_isChange'\s*:\s*'([A-F0-9]+)'",
            r'"key_check_isChange"\s*:\s*"([A-F0-9]+)"',
        ]

        for pattern in key_check_patterns:
            key_check_match = re.search(pattern, html_content)
            if key_check_match:
                self.key_check_ischange = key_check_match.group(1)
                self.logger.info(f"获取到key_check_isChange: {self.key_check_ischange}")
                break

        # 提取leftTicketStr
        leftticket_patterns = [
            r"'leftTicketStr'\s*:\s*'([^']+)'",
            r'"leftTicketStr"\s*:\s*"([^"]+)"',
        ]
        for pattern in leftticket_patterns:
            leftticket_match = re.search(pattern, html_content)
            if leftticket_match:
                train_info['leftTicket'] = leftticket_match.group(1)
                self.logger.info(f"更新leftTicketStr")
                break

    def check_order_info(self, passenger, repeat_submit_token):
        """检查订单信息"""
        try:
            url = "https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo"

            passenger_ticket_str = f"O,0,1,{passenger['passenger_name']},1,{passenger['passenger_id_no']},{passenger['mobile_no']},N,{passenger['allEncStr']}"
            old_passenger_str = f"{passenger['passenger_name']},1,{passenger['passenger_id_no']},1_"

            data = {
                'cancel_flag': '2',
                'bed_level_order_num': '000000000000000000000000000000',
                'passengerTicketStr': passenger_ticket_str,
                'oldPassengerStr': old_passenger_str,
                'tour_flag': 'dc',
                'whatsSelect': '1',
                'sessionId': '',
                'sig': '',
                'scene': 'nc_login',
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': repeat_submit_token or ''
            }

            self.logger.info("检查订单信息...")
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"checkOrderInfo响应状态: {result.get('status')}")

                if result.get('status') and result.get('data', {}).get('submitStatus'):
                    return True, result
                else:
                    self.logger.error(f"订单信息检查失败")
                    return False, result
            else:
                self.logger.error(f"checkOrderInfo HTTP错误: {response.status_code}")
                return False, None

        except Exception as e:
            self.logger.error(f"检查订单信息异常: {e}")
            return False, None

    def confirm_order_queue(self, passenger, train_info, repeat_submit_token, key_check_ischange):
        """确认订单队列"""
        try:
            if not key_check_ischange:
                self.logger.error("缺少key_check_isChange参数")
                return False, {'error': '缺少key_check_isChange参数'}

            if not repeat_submit_token:
                self.logger.error("缺少REPEAT_SUBMIT_TOKEN")
                return False, {'error': '缺少REPEAT_SUBMIT_TOKEN'}

            url = "https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue"

            passenger_ticket_str = f"O,0,1,{passenger['passenger_name']},1,{passenger['passenger_id_no']},{passenger['mobile_no']},N,{passenger['allEncStr']}"
            old_passenger_str = f"{passenger['passenger_name']},1,{passenger['passenger_id_no']},1_"

            data = {
                'passengerTicketStr': passenger_ticket_str,
                'oldPassengerStr': old_passenger_str,
                'purpose_codes': '00',
                'key_check_isChange': key_check_ischange,
                'leftTicketStr': train_info.get('leftTicket', ''),
                'train_location': train_info.get('train_location', ''),
                'choose_seats': '',
                'seatDetailType': '000',
                'is_jy': 'N',
                'is_cj': 'Y',
                'encryptedData': '',
                'whatsSelect': '1',
                'roomType': '00',
                'dwAll': 'N',
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': repeat_submit_token
            }

            self.logger.info("提交订单到排队系统...")
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"confirmSingleForQueue响应: {result}")

                data_field = result.get('data')
                if isinstance(data_field, str):
                    self.logger.error(f"提交订单失败: {data_field}")
                    return False, result

                if result.get('status') and isinstance(data_field, dict) and data_field.get('submitStatus'):
                    self.logger.info("订单已成功提交到排队系统")
                    return True, result
                else:
                    self.logger.error(f"提交订单失败")
                    return False, result
            else:
                self.logger.error(f"confirmSingleForQueue HTTP错误: {response.status_code}")
                return False, None

        except Exception as e:
            self.logger.error(f"确认订单队列异常: {e}")
            return False, None

    def poll_order_status(self, repeat_submit_token, max_wait_time=300):
        """轮询订单状态"""
        from .order_query_service import OrderQueryService
        
        query_service = OrderQueryService(self.session, self.logger)
        
        self.logger.info(f"开始轮询订单状态，最大等待时间: {max_wait_time}秒")

        start_time = time.time()
        poll_interval = 2

        while time.time() - start_time < max_wait_time:
            status, data = query_service.query_order_wait_time(repeat_submit_token)

            if status == 'completed':
                self.logger.info("订单处理完成")
                order_id = data.get('orderId')
                if order_id:
                    final_result = query_service.get_order_result(order_id, repeat_submit_token)
                    if final_result:
                        self.logger.info("订单最终提交成功!")
                        return True, final_result
                return True, data
            elif status == 'failed':
                self.logger.error("订单处理失败!")
                return False, data
            elif status == 'waiting':
                pass
            else:
                self.logger.error("查询订单状态出错")
                return False, data

            time.sleep(poll_interval)

        self.logger.warning("订单轮询超时")
        return False, None
