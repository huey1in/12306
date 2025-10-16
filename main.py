#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""主程序入口"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import setup_logging, STATION_MAPPING, get_logger
from src.services import (
    TrainTicketDebugger,
    AuthService,
    CookieService,
    OrderQueryService,
    OrderSubmitService,
    GrabTicketService
)
import requests


class TrainOrderManager:
    """火车订票管理器"""
    
    def __init__(self):
        """初始化订单管理器"""
        # 设置日志
        self.logger = setup_logging()
        
        self.station_mapping = STATION_MAPPING

        # 创建独立的session用于订单
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })

        # 订单相关配置
        self.order_config = {
            'preferred_trains': [],
            'preferred_seat_types': ['二等座', '一等座']
        }

        # 创建查询器
        self.ticket_debugger = self._create_ticket_debugger()

        # 订单状态
        self.current_train_info = None
        self.current_seat_type = None
        self.passengers_data = None
        self._target_train_no = None
        self._target_seat_type = None
        self._auto_select_passenger = False

        # 初始化服务
        self.auth_service = AuthService(self.session, self.logger)
        self.cookie_service = CookieService(self.session, self.logger)
        self.order_query_service = OrderQueryService(self.session, self.logger)
        self.order_submit_service = OrderSubmitService(self.session, self.logger)
        self.grab_ticket_service = GrabTicketService(self.session, self.logger)

        # 加载cookies
        self.load_cookies()

    def _create_ticket_debugger(self):
        """创建票务查询器"""
        config = {
            'base_url': 'https://kyfw.12306.cn/otn/leftTicket/query',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init'
            },
            'query_params': {
                'leftTicketDTO.train_date': '',
                'leftTicketDTO.from_station': '',
                'leftTicketDTO.to_station': '',
                'purpose_codes': 'ADULT'
            }
        }

        debugger = TrainTicketDebugger(
            config=config,
            session=self.session,
            station_mapping=self.station_mapping,
            logger=self.logger
        )

        return debugger

    def load_cookies(self, filename='cookies.pkl'):
        """加载cookies"""
        return self.cookie_service.load_cookies(filename)

    def save_cookies(self, filename='cookies.pkl'):
        """保存cookies"""
        return self.cookie_service.save_cookies(filename)

    def check_login_status(self):
        """检查登录状态"""
        return self.auth_service.check_login_status()

    def login_process(self):
        """完整的登录流程"""
        return self.auth_service.login_process()

    def get_login_user_name(self):
        """获取当前登录用户的姓名"""
        return self.auth_service.get_login_user_name()

    def query_available_trains(self):
        """查询可用车次"""
        self.logger.info("开始查询可用车次...")
        response_data = self.ticket_debugger.make_request()

        if not response_data or not response_data.get('status'):
            self.logger.error("查询车次失败")
            return None

        results = response_data.get('data', {}).get('result', [])
        if not results:
            self.logger.warning("没有找到可用车次")
            return None

        # 解析车次信息
        available_trains = []
        for result in results:
            train_info = self.ticket_debugger.decode_train_info(result)
            if train_info:
                parts = result.split('|')
                train_info['secretStr'] = parts[0]
                train_info['seat_discount_info'] = 'M0097O0097W0097'
                available_trains.append(train_info)

        self.logger.info(f"找到 {len(available_trains)} 趟可用车次")
        return available_trains

    def get_seat_type_code(self, seat_type_name):
        """获取座位类型代码"""
        seat_mapping = {
            '商务座': '9',
            '一等座': 'M',
            '二等座': 'O',
            '硬卧': '3',
            '软卧': '4',
            '硬座': '1',
            '无座': '1'
        }
        return seat_mapping.get(seat_type_name, 'O')

    def select_train_manually(self, available_trains):
        """手动选择车次和座位"""
        from src.utils import format_seat_display

        print("\n可用车次列表：")
        print("="*100)
        print(f"{'序号':<4} {'车次':<10} {'出发时间':<10} {'到达时间':<10} {'历时':<10} {'商务座':<8} {'一等座':<8} {'二等座':<8} {'硬卧':<8} {'软卧':<8} {'硬座':<8}")
        print("="*100)

        for idx, train in enumerate(available_trains, 1):
            print(f"{idx:<4} {train.get('列车号', ''):<10} {train.get('出发时间', ''):<10} {train.get('到达时间', ''):<10} {train.get('历时', ''):<10} "
                  f"{format_seat_display(train.get('商务座', '--')):<8} {format_seat_display(train.get('一等座', '--')):<8} {format_seat_display(train.get('二等座', '--')):<8} "
                  f"{format_seat_display(train.get('硬卧', '--')):<8} {format_seat_display(train.get('软卧', '--')):<8} {format_seat_display(train.get('硬座', '--')):<8}")
        print("="*100)

        # 选择车次
        while True:
            try:
                choice = input(f"\n请选择车次 (1-{len(available_trains)}): ").strip()
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(available_trains):
                    selected_train = available_trains[choice_idx]
                    break
                else:
                    print(f"请输入 1 到 {len(available_trains)} 之间的数字")
            except (ValueError, KeyboardInterrupt):
                print("输入无效，请输入数字")

        # 获取该车次可用的座位类型
        available_seats = []
        seat_types = ['商务座', '一等座', '二等座', '硬卧', '软卧', '硬座']
        for seat_type in seat_types:
            seat_value = selected_train.get(seat_type, '--')
            if seat_value and seat_value != '无' and seat_value != '--' and seat_value != '*':
                available_seats.append(seat_type)

        if not available_seats:
            print("该车次没有可用座位")
            return None, None

        # 选择座位类型
        print(f"\n车次 {selected_train.get('列车号')} 可用座位类型：")
        for idx, seat_type in enumerate(available_seats, 1):
            print(f"{idx}. {seat_type} - 余票: {selected_train.get(seat_type)}")

        while True:
            try:
                choice = input(f"\n请选择座位类型 (1-{len(available_seats)}): ").strip()
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(available_seats):
                    seat_type = available_seats[choice_idx]
                    print(f"已选择: {selected_train.get('列车号')} {seat_type}")
                    self.logger.info(f"用户选择车次: {selected_train.get('列车号')}, 座位类型: {seat_type}")
                    return selected_train, seat_type
                else:
                    print(f"请输入 1 到 {len(available_seats)} 之间的数字")
            except (ValueError, KeyboardInterrupt):
                print("输入无效，请输入数字")

    def query_trains_only(self):
        """仅查询车次信息，不订票"""
        try:
            self.logger.info("开始查询车次")

            print("\n请输入查询参数：")

            train_date = input("出发日期 (格式: YYYY-MM-DD): ").strip()
            if not train_date:
                print("出发日期不能为空")
                return False

            from_station_name = input("出发站: ").strip()
            if not from_station_name:
                print("出发站不能为空")
                return False

            to_station_name = input("到达站: ").strip()
            if not to_station_name:
                print("到达站不能为空")
                return False

            # 查找站点代码
            from_station_code = None
            to_station_code = None

            for name, code in self.station_mapping.items():
                if name == from_station_name:
                    from_station_code = code
                if name == to_station_name:
                    to_station_code = code

            if not from_station_code:
                print(f"未找到出发站 '{from_station_name}' 的代码")
                return False

            if not to_station_code:
                print(f"未找到到达站 '{to_station_name}' 的代码")
                return False

            # 更新查询参数
            self.ticket_debugger.query_params['leftTicketDTO.train_date'] = train_date
            self.ticket_debugger.query_params['leftTicketDTO.from_station'] = from_station_code
            self.ticket_debugger.query_params['leftTicketDTO.to_station'] = to_station_code

            print(f"\n查询参数:")
            print(f"  日期: {train_date}")
            print(f"  出发站: {from_station_name} ({from_station_code})")
            print(f"  到达站: {to_station_name} ({to_station_code})")

            print("\n正在查询车次...")
            response_data = self.ticket_debugger.debug()

            if response_data and response_data.get('status'):
                print("\n查询完成！")
                return True
            else:
                print("\n查询失败")
                return False

        except Exception as e:
            self.logger.error(f"查询车次异常: {e}")
            print(f"查询过程中发生错误: {e}")
            return False

    def auto_book_ticket(self):
        """自动订票主流程"""
        try:
            self.logger.info("开始自动订票流程")

            print("\n请输入查询参数：")

            train_date = input("出发日期: ").strip()
            if not train_date:
                print("出发日期不能为空")
                return False

            from_station_name = input("出发站: ").strip()
            if not from_station_name:
                print("出发站不能为空")
                return False

            to_station_name = input("到达站: ").strip()
            if not to_station_name:
                print("到达站不能为空")
                return False

            # 查找站点代码
            from_station_code = None
            to_station_code = None

            for name, code in self.station_mapping.items():
                if name == from_station_name:
                    from_station_code = code
                if name == to_station_name:
                    to_station_code = code

            if not from_station_code:
                print(f"未找到出发站 '{from_station_name}' 的代码")
                return False

            if not to_station_code:
                print(f"未找到到达站 '{to_station_name}' 的代码")
                return False

            # 更新查询参数
            self.ticket_debugger.query_params['leftTicketDTO.train_date'] = train_date
            self.ticket_debugger.query_params['leftTicketDTO.from_station'] = from_station_code
            self.ticket_debugger.query_params['leftTicketDTO.to_station'] = to_station_code

            print(f"\n查询参数已设置:")
            print(f"  日期: {train_date}")
            print(f"  出发站: {from_station_name} ({from_station_code})")
            print(f"  到达站: {to_station_name} ({to_station_code})")

            # 清空抢票模式的标记
            self._target_train_no = None
            self._target_seat_type = None
            self._auto_select_passenger = False

            # 调用执行流程
            return self._execute_booking_flow(from_station_code, to_station_code, train_date, 
                                             from_station_name, to_station_name)

        except Exception as e:
            self.logger.error(f"自动订票流程异常: {e}")
            print(f"订票过程中发生错误: {e}")
            return False

    def _execute_booking_flow(self, from_station, to_station, train_date, from_name, to_name):
        """执行订票流程核心逻辑"""
        try:
            # 1. 查询车次
            print("\n正在查询可用车次...")
            available_trains = self.query_available_trains()
            if not available_trains:
                print("没有找到可用车次")
                return False

            # 选择车次
            if self._target_train_no and self._target_seat_type:
                selected_train = None
                for train in available_trains:
                    if train.get('列车号') == self._target_train_no:
                        selected_train = train
                        break

                if not selected_train:
                    print(f"未找到目标车次: {self._target_train_no}")
                    return False

                seat_type = self._target_seat_type
                print(f"自动选择车次: {selected_train.get('列车号')} {seat_type}")
            else:
                selected_train, seat_type = self.select_train_manually(available_trains)
                if not selected_train:
                    print("没有选择车次")
                    return False

            self.current_train_info = selected_train
            self.current_seat_type = seat_type

            # 2. 检查登录状态
            print("\n正在检查登录状态...")
            if not self.check_login_status():
                print("登录验证失败 - 需要重新登录")

                while True:
                    choice = input("\n是否立即登录? (y/n): ").strip().lower()
                    if choice == 'y':
                        if self.login_process():
                            print("\n登录成功，继续订票流程...")
                            self.save_cookies()
                            break
                        else:
                            print("\n登录失败，无法继续订票")
                            return False
                    elif choice == 'n':
                        print("\n已取消订票，请先登录后再试")
                        return False

            print("登录状态正常，开始订票流程...")

            # 3. 提交订单
            print("正在提交订单...")
            success, result = self.order_submit_service.submit_order_request(
                selected_train, seat_type, from_station, to_station, 
                train_date, from_name, to_name
            )
            if not success:
                print("订单提交失败")
                return False

            # 4. 获取乘客信息
            if not self.passengers_data:
                print("正在获取乘客信息...")
                success, passengers = self.order_query_service.get_passengers(
                    self.order_submit_service.repeat_submit_token
                )
                if not success or not passengers:
                    print("获取乘客信息失败")
                    return False

                # 选择乘客
                if self._auto_select_passenger:
                    login_user_name = self.get_login_user_name()
                    selected_passenger = None

                    if login_user_name:
                        for p in passengers:
                            if p.get('passenger_name') == login_user_name:
                                selected_passenger = p
                                print(f"使用登录用户: {login_user_name}")
                                break

                    if not selected_passenger:
                        selected_passenger = passengers[0]
                        print(f"使用第一个乘客: {selected_passenger['passenger_name']}")

                    self.passengers_data = [selected_passenger]
                else:
                    print("\n可用乘客列表：")
                    for idx, p in enumerate(passengers, 1):
                        print(f"{idx}. {p['passenger_name']} - {p['passenger_id_type_name']} - {p['passenger_id_no']}")

                    while True:
                        try:
                            choice = input(f"\n请选择乘客 (1-{len(passengers)}): ").strip()
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(passengers):
                                selected_passenger = passengers[choice_idx]
                                print(f"已选择乘客: {selected_passenger['passenger_name']}")
                                self.passengers_data = [selected_passenger]
                                break
                            else:
                                print(f"请输入 1 到 {len(passengers)} 之间的数字")
                        except (ValueError, KeyboardInterrupt):
                            print("输入无效，请输入数字")
                print()
            else:
                print(f"使用预选乘客: {self.passengers_data[0].get('passenger_name')}")

            # 5. 检查订单信息
            print("正在检查订单信息...")
            success, result = self.order_submit_service.check_order_info(
                self.passengers_data[0],
                self.order_submit_service.repeat_submit_token
            )
            if not success:
                print("订单信息检查失败")
                return False

            # 6. 获取排队人数
            print("正在查询排队人数...")
            seat_type_code = self.get_seat_type_code(seat_type)
            success, result = self.order_query_service.get_queue_count(
                selected_train, seat_type_code, from_station, to_station,
                train_date, self.order_submit_service.repeat_submit_token
            )
            if not success:
                print("获取排队人数失败")
                return False

            # 7. 验证关键参数
            if not self.order_submit_service.key_check_ischange:
                print("缺少关键参数 key_check_isChange")
                return False

            if not self.order_submit_service.repeat_submit_token:
                print("缺少 REPEAT_SUBMIT_TOKEN")
                return False

            print(f"关键参数验证通过:")
            print(f"  - key_check_isChange: {self.order_submit_service.key_check_ischange[:20]}...")
            print(f"  - REPEAT_SUBMIT_TOKEN: {self.order_submit_service.repeat_submit_token[:20]}...")

            # 8. 确认订单队列
            print("\n正在提交订单到排队系统...")
            success, result = self.order_submit_service.confirm_order_queue(
                self.passengers_data[0],
                selected_train,
                self.order_submit_service.repeat_submit_token,
                self.order_submit_service.key_check_ischange
            )
            if not success:
                print("提交订单到排队系统失败")
                return False

            # 9. 轮询订单状态
            print("正在排队，请等待...")
            success, final_result = self.order_submit_service.poll_order_status(
                self.order_submit_service.repeat_submit_token
            )

            if success:
                print("订票成功！请及时支付订单")
                return True
            else:
                print("订票失败")
                return False

        except Exception as e:
            self.logger.error(f"订票流程执行异常: {e}")
            print(f"订票过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def scheduled_grab_ticket(self):
        """定时抢票功能"""
        return self.grab_ticket_service.execute_grab_ticket(self)


def main():
    """主函数"""
    try:
        # 打印ASCII艺术字
        print("""
  ██╗    ██████╗  ██████╗  ██████╗   ██████╗
 ███║    ╚════██╗ ╚════██╗ ██╔═████╗ ██╔════╝
 ╚██║     █████╔╝  █████╔╝ ██║██╔██║ ███████╗
  ██║    ██╔═══╝   ╚═══██╗ ████╔╝██║ ██╔═══██╗
  ██║    ███████╗ ██████╔╝ ╚██████╔╝ ╚██████╔╝
  ╚═╝    ╚══════╝ ╚═════╝   ╚═════╝   ╚═════╝

                                  Hacker: 1in
        """)

        print("\n正在加载...")
        order_manager = TrainOrderManager()

        while True:
            print("\n选择操作:")
            print("1. 查询")
            print("2. 订票")
            print("3. 抢票")
            print("4. 退出")

            choice = input("\n请输入选择 (1-4): ").strip()

            if choice == '1':
                order_manager.query_trains_only()
            elif choice == '2':
                success = order_manager.auto_book_ticket()
                if success:
                    print("\n订票流程完成！")
                else:
                    print("\n订票失败，请检查日志文件")
            elif choice == '3':
                success = order_manager.scheduled_grab_ticket()
                if success:
                    print("\n抢票成功！")
                else:
                    print("\n抢票失败，请检查日志文件")
            elif choice == '4':
                print("退出程序")
                order_manager.logger.info("程序正常退出")
                break
            else:
                print("无效选择")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序发生错误: {e}")


if __name__ == '__main__':
    main()
