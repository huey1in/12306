#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""定时抢票服务模块"""

import time
from datetime import datetime
from src.utils import get_logger


class GrabTicketService:
    """定时抢票服务"""
    
    def __init__(self, session=None, logger=None):
        """
        初始化抢票服务
        
        Args:
            session: requests会话对象
            logger: 日志记录器
        """
        self.session = session
        self.logger = logger or get_logger('12306')

    def execute_grab_ticket(self, order_manager):
        """
        执行定时抢票流程
        
        Args:
            order_manager: TrainOrderManager实例
            
        Returns:
            bool: 抢票是否成功
        """
        try:
            self.logger.info("开始定时抢票流程")

            # 1. 输入查询参数
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

            for name, code in order_manager.station_mapping.items():
                if name == from_station_name:
                    from_station_code = code
                if name == to_station_name:
                    to_station_code = code

            if not from_station_code:
                print(f"未找到出发站 '{from_station_name}' 的代码，请检查站名")
                return False

            if not to_station_code:
                print(f"未找到到达站 '{to_station_name}' 的代码，请检查站名")
                return False

            # 2. 输入开售时间
            print("\n请输入车票开售时间：")
            sale_time = input("开售时间 (格式: HH:MM:SS，如 15:00:00): ").strip()
            if not sale_time:
                print("开售时间不能为空")
                return False

            try:
                # 使用今天的日期
                today = datetime.now().strftime("%Y-%m-%d")
                sale_datetime_str = f"{today} {sale_time}"
                sale_datetime = datetime.strptime(sale_datetime_str, "%Y-%m-%d %H:%M:%S")

                # 检查开售时间是否已过
                if sale_datetime < datetime.now():
                    print(f"警告: 开售时间 {sale_datetime_str} 已经过去")
                    confirm = input("是否继续? (y/n): ").strip().lower()
                    if confirm != 'y':
                        return False
                else:
                    print(f"车票将在今天 {sale_time} 开售")
            except ValueError:
                print("时间格式错误，请使用 HH:MM:SS 格式，如 15:00:00")
                return False

            # 3. 更新查询参数并查询车次
            order_manager.ticket_debugger.query_params['leftTicketDTO.train_date'] = train_date
            order_manager.ticket_debugger.query_params['leftTicketDTO.from_station'] = from_station_code
            order_manager.ticket_debugger.query_params['leftTicketDTO.to_station'] = to_station_code

            print(f"\n查询参数已设置:")
            print(f"  日期: {train_date}")
            print(f"  出发站: {from_station_name} ({from_station_code})")
            print(f"  到达站: {to_station_name} ({to_station_code})")

            print("\n正在查询车次信息...")
            available_trains = order_manager.query_available_trains()
            if not available_trains:
                print("没有找到车次")
                return False

            # 4. 选择车次（显示所有车次，包括未开售的）
            print("\n车次列表（包括未开售）：")
            print("="*100)
            print(f"{'序号':<4} {'车次':<10} {'出发时间':<10} {'到达时间':<10} {'历时':<10} {'商务座':<8} {'一等座':<8} {'二等座':<8}")
            print("="*100)

            def format_seat(value):
                if value == '*':
                    return '未开售'
                elif not value or value == '--':
                    return '--'
                return value

            for idx, train in enumerate(available_trains, 1):
                print(f"{idx:<4} {train.get('列车号', ''):<10} {train.get('出发时间', ''):<10} {train.get('到达时间', ''):<10} {train.get('历时', ''):<10} "
                      f"{format_seat(train.get('商务座', '--')):<8} {format_seat(train.get('一等座', '--')):<8} {format_seat(train.get('二等座', '--')):<8}")
            print("="*100)

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

            # 5. 选择座位类型
            print("\n请选择座位类型：")
            print("1. 二等座")
            print("2. 一等座")
            while True:
                seat_choice = input("请选择 (1-2): ").strip()
                if seat_choice == '1':
                    seat_type = '二等座'
                    break
                elif seat_choice == '2':
                    seat_type = '一等座'
                    break
                else:
                    print("请输入 1 或 2")

            print(f"\n已选择: {selected_train.get('列车号')} {seat_type}")

            # 6. 等待到开售前1小时，提示用户登录
            print(f"\n等待开售时间: {sale_datetime_str}")
            print(f"车次: {selected_train.get('列车号')}")
            print(f"座位: {seat_type}")
            print(f"提示: 开售前1小时将提示登录获取cookie")

            login_prompted = False  # 标记是否已提示登录

            while True:
                now = datetime.now()
                time_diff = (sale_datetime - now).total_seconds()

                # 开售前1小时提示登录
                if time_diff <= 3600 and not login_prompted:
                    print(f"\n{' '*80}")  # 清除倒计时行
                    print("\n=== 距离开售还有1小时，请立即登录获取cookie ===\n")

                    while True:
                        choice = input("是否立即登录? (y/n): ").strip().lower()
                        if choice == 'y':
                            if order_manager.login_process():
                                print("\n登录成功！Cookie已保存")

                                # 获取当前登录用户信息
                                login_user_name = order_manager.get_login_user_name()

                                # 获取乘客列表并预选乘客
                                print("正在获取乘客信息...")
                                success, passengers = order_manager.order_query_service.get_passengers(None)
                                if success and passengers:
                                    # 尝试找到登录用户对应的乘客
                                    selected_passenger = None
                                    if login_user_name:
                                        for p in passengers:
                                            if p.get('passenger_name') == login_user_name:
                                                selected_passenger = p
                                                print(f"\n抢票将使用登录用户: {login_user_name}")
                                                break

                                    # 如果没找到，使用第一个乘客
                                    if not selected_passenger:
                                        selected_passenger = passengers[0]
                                        if login_user_name:
                                            print(f"\n登录用户 '{login_user_name}' 不在乘客列表中")
                                        print(f"抢票将使用第一个乘客: {selected_passenger.get('passenger_name')}")

                                    # 预先设置乘客信息
                                    order_manager.passengers_data = [selected_passenger]
                                    order_manager._auto_select_passenger = True  # 标记已自动选择
                                else:
                                    print("警告: 无法获取乘客信息，将在抢票时重新获取")

                                print("\n继续等待开售...")
                                login_prompted = True
                                break
                            else:
                                print("\n登录失败，请重试")
                        elif choice == 'n':
                            print("\n警告: 未登录可能导致抢票失败")
                            confirm = input("确认跳过登录? (y/n): ").strip().lower()
                            if confirm == 'y':
                                login_prompted = True
                                break
                        else:
                            print("请输入 y 或 n")

                if time_diff > 0:
                    # 格式化时间显示
                    hours = int(time_diff // 3600)
                    minutes = int((time_diff % 3600) // 60)
                    seconds = int(time_diff % 60)

                    if hours > 0:
                        time_str = f"{hours}小时{minutes}分{seconds}秒"
                    elif minutes > 0:
                        time_str = f"{minutes}分{seconds}秒"
                    else:
                        time_str = f"{seconds}秒"

                    print(f"\r距离开售还有: {time_str}     ", end='', flush=True)
                    time.sleep(1)
                else:
                    print("\n\n开始抢票！")
                    break

            # 7. 开售时间到达，执行完整的订票流程
            print("\n开始执行订票流程...\n")

            # 将抢票参数设置到查询参数中
            order_manager.ticket_debugger.query_params['leftTicketDTO.train_date'] = train_date
            order_manager.ticket_debugger.query_params['leftTicketDTO.from_station'] = from_station_code
            order_manager.ticket_debugger.query_params['leftTicketDTO.to_station'] = to_station_code

            # 设置目标车次和座位类型，用于自动选择
            order_manager._target_train_no = selected_train.get('列车号')
            order_manager._target_seat_type = seat_type
            order_manager._auto_select_passenger = True  # 标记为自动选择第一个乘客

            # 调用完整的订票流程
            return order_manager._execute_booking_flow(
                from_station_code, to_station_code, train_date,
                from_station_name, to_station_name
            )

        except KeyboardInterrupt:
            print("\n\n抢票被用户中断")
            self.logger.info("抢票被用户中断")
            return False
        except Exception as e:
            self.logger.error(f"定时抢票流程异常: {e}")
            import traceback
            traceback.print_exc()
            print(f"抢票过程中发生错误: {e}")
            return False
