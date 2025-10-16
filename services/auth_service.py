#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""登录认证服务模块"""

import json
import requests
import getpass
from utils import get_logger, encrypt_password


class AuthService:
    """12306认证服务"""
    
    def __init__(self, session=None, logger=None):
        """
        初始化认证服务
        
        Args:
            session: requests会话对象
            logger: 日志记录器
        """
        self.session = session if session is not None else requests.Session()
        self.logger = logger or get_logger('12306')

    def visit_login_page(self):
        """访问登录页面获取初始cookies"""
        try:
            self.logger.info("访问登录页面...")
            response = self.session.get("https://kyfw.12306.cn/", timeout=30)
            self.logger.info(f"主页访问状态码: {response.status_code}")

            response = self.session.get("https://kyfw.12306.cn/otn/resources/login.html", timeout=30)
            self.logger.info(f"登录页访问状态码: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"访问登录页面失败: {e}")
            return False

    def check_login_verify(self, username):
        """检查登录验证方式"""
        try:
            url = "https://kyfw.12306.cn/passport/web/checkLoginVerify"

            headers = self.session.headers.copy()
            headers.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            })

            data = {
                'username': username,
                'appid': 'otn'
            }

            self.logger.info(f"checkLoginVerify请求参数: {data}")
            response = self.session.post(url, data=data, headers=headers, timeout=30)

            self.logger.info(f"checkLoginVerify响应状态码: {response.status_code}")
            self.logger.info(f"checkLoginVerify响应内容: {response.text}")

            if response.status_code == 200:
                result = response.json()
                if result.get('result_code') == 0 or result.get('result_code') == '0':
                    self.logger.info("checkLoginVerify成功")
                    return True, result
                else:
                    self.logger.error(f"checkLoginVerify失败: {result.get('result_message', '未知错误')}")
                    return False, result
            return False, None
        except Exception as e:
            self.logger.error(f"检查登录验证失败: {e}")
            return False, None

    def get_sms_code(self, phone, id_last_four):
        """获取短信验证码"""
        try:
            url = "https://kyfw.12306.cn/passport/web/getMessageCode"
            data = {
                'appid': 'otn',
                'username': phone,
                'castNum': id_last_four
            }
            self.logger.info(f"发送验证码请求参数: {data}")
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"发送短信验证码响应: {result}")
                if result.get('result_code') == 0 or result.get('result_code') == '0':
                    return True, result
                else:
                    self.logger.error(f"发送验证码失败: {result.get('result_message', '未知错误')}")
                    return False, result
            return False, None
        except Exception as e:
            self.logger.error(f"发送短信验证码失败: {e}")
            return False, None

    def login_with_sms(self, phone, sms_code, password):
        """使用短信验证码登录"""
        try:
            url = "https://kyfw.12306.cn/passport/web/login"

            # 加密密码
            encrypted_password = ''
            if password:
                self.logger.info("正在加密密码...")
                encrypted_password = encrypt_password(password)
                if not encrypted_password:
                    self.logger.error("密码加密失败")
                    return False, None
                self.logger.info(f"密码加密成功: {encrypted_password[:30]}...")

            # 更新请求头
            headers = self.session.headers.copy()
            headers.update({
                'isPasswordCopy': 'N',
                'appFlag': '',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            })

            # 登录参数
            data = {
                'sessionId': '',
                'sig': '',
                'if_check_slide_passcode_token': '',
                'scene': '',
                'checkMode': '0',  # 0表示密码+验证码模式
                'randCode': sms_code,  # 短信验证码
                'username': phone,
                'password': encrypted_password,  # 加密后的密码
                'appid': 'otn'
            }

            self.logger.info(f"登录请求参数: {data}")
            response = self.session.post(url, data=data, headers=headers, timeout=30)

            self.logger.info(f"登录响应状态码: {response.status_code}")
            self.logger.info(f"登录响应内容: {response.text}")

            if response.status_code == 200:
                result = response.json()

                if result.get('result_code') == 0 or result.get('result_code') == '0':
                    self.logger.info("登录成功!")
                    uamtk = result.get('uamtk', '')
                    self.logger.info(f"获取到uamtk: {uamtk}")

                    if uamtk:
                        return self.auth_uamtk(uamtk)
                    return True, result
                else:
                    self.logger.error(f"登录失败: {result.get('result_message', '未知错误')}")
                    return False, result
            return False, None
        except Exception as e:
            self.logger.error(f"登录失败: {e}")
            return False, None

    def auth_uamtk(self, uamtk):
        """使用uamtk获取认证token"""
        try:
            url = "https://kyfw.12306.cn/passport/web/auth/uamtk"
            data = {'appid': 'otn'}
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"UAMTK认证响应: {result}")

                if result.get('result_code') == 0 or result.get('result_code') == '0':
                    new_apptk = result.get('newapptk')
                    if new_apptk:
                        return self.auth_uamauthclient(new_apptk)
            return False, None
        except Exception as e:
            self.logger.error(f"UAMTK认证失败: {e}")
            return False, None

    def auth_uamauthclient(self, apptk):
        """使用apptk完成最终认证"""
        try:
            url = "https://kyfw.12306.cn/otn/uamauthclient"
            data = {'tk': apptk}
            response = self.session.post(url, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"最终认证响应: {result}")

                if result.get('result_code') == 0 or result.get('result_code') == '0':
                    username = result.get('username')
                    self.logger.info(f"认证成功，用户: {username}")
                    return True, result
            return False, None
        except Exception as e:
            self.logger.error(f"最终认证失败: {e}")
            return False, None

    def check_login_status(self):
        """检查登录状态"""
        try:
            self.logger.info("检查登录状态...")

            # 首先检查是否有必要的认证cookie
            has_tk = 'tk' in self.session.cookies
            has_ukey = 'uKey' in self.session.cookies

            self.logger.info(f"认证cookie检查 - tk: {has_tk}, uKey: {has_ukey}")

            if not has_tk:
                self.logger.warning("缺少tk认证cookie，需要重新登录")
                return False

            url = "https://kyfw.12306.cn/otn/login/checkUser"

            # 保存checkUser前的所有cookies
            saved_cookies = dict(self.session.cookies)
            self.logger.info(f"checkUser前JSESSIONID: {saved_cookies.get('JSESSIONID')}")

            response = self.session.post(url, timeout=30)

            # checkUser会改变JSESSIONID,我们需要恢复原始的
            jsessionid_after = self.session.cookies.get('JSESSIONID')
            if saved_cookies.get('JSESSIONID') != jsessionid_after:
                self.logger.warning(f"checkUser改变了JSESSIONID: {saved_cookies.get('JSESSIONID')} -> {jsessionid_after}")
                # 恢复登录时的cookies
                self.session.cookies.clear()
                self.session.cookies.update(saved_cookies)
                self.logger.info(f"已恢复登录时的JSESSIONID: {self.session.cookies.get('JSESSIONID')}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    self.logger.info(f"checkUser响应: {result}")

                    if result.get('status'):
                        data = result.get('data', {})
                        if isinstance(data, dict) and data.get('flag'):
                            self.logger.info("用户已登录且认证完整")
                            return True
                        else:
                            self.logger.warning(f"checkUser返回status=true但data异常: {data}")
                            return False
                    else:
                        self.logger.warning(f"用户未登录，checkUser返回: {result}")
                        return False

                except json.JSONDecodeError as e:
                    self.logger.error(f"解析登录状态响应失败: {e}")
                    self.logger.error(f"响应内容: {response.text[:500]}")
                    return False
            else:
                self.logger.error(f"检查登录状态HTTP错误: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"检查登录状态异常: {e}")
            return False

    def login_process(self):
        """完整的登录流程"""
        try:
            print("\n开始登录流程...")

            if not self.visit_login_page():
                print("访问登录页面失败")
                return False

            print("\n请输入登录信息：")
            phone_number = input("手机号: ").strip()
            if not phone_number:
                print("手机号不能为空")
                return False

            id_last_four = input("证件号后四位: ").strip()
            if not id_last_four or len(id_last_four) != 4:
                print("请输入正确的证件号后四位")
                return False

            print("\n正在检查登录验证方式...")
            success, result = self.check_login_verify(phone_number)
            if not success:
                print("检查登录验证方式失败")
                return False

            print("正在发送短信验证码...")
            success, result = self.get_sms_code(phone_number, id_last_four)
            if not success:
                print("发送短信验证码失败")
                return False

            print("短信验证码已发送，请查收")
            sms_code = input("\n请输入收到的短信验证码: ").strip()
            if not sms_code:
                print("验证码不能为空")
                return False

            print("\n12306需要密码+验证码组合登录")
            password = getpass.getpass("请输入12306登录密码: ").strip()
            if not password:
                print("密码不能为空")
                return False

            print("\n正在登录...")
            success, result = self.login_with_sms(phone_number, sms_code, password)
            if not success:
                print("登录失败")
                return False

            print("\n登录成功！")
            return True

        except KeyboardInterrupt:
            print("\n登录被用户中断")
            return False
        except Exception as e:
            self.logger.error(f"登录流程异常: {e}")
            print(f"登录过程中发生错误: {e}")
            return False

    def get_login_user_name(self):
        """获取当前登录用户的姓名"""
        try:
            url = "https://kyfw.12306.cn/otn/modifyUser/queryLoginUser"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') and data.get('data'):
                    user_data = data.get('data')
                    # 尝试获取用户姓名
                    name = user_data.get('name') or user_data.get('user_name')
                    if name:
                        self.logger.info(f"获取到登录用户姓名: {name}")
                        return name
        except Exception as e:
            self.logger.warning(f"获取登录用户信息失败: {e}")

        return None
