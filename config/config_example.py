#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 项目配置文件示例

# API配置示例
CONFIG_EXAMPLE = {
    'api': {
        'base_url': 'https://kyfw.12306.cn/otn/leftTicket/query',
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init'
        }
    },
    'query_params': {
        'leftTicketDTO.train_date': '',  # 出发日期 (YYYY-MM-DD)
        'leftTicketDTO.from_station': '',  # 出发站代码
        'leftTicketDTO.to_station': '',  # 到达站代码
        'purpose_codes': 'ADULT'  # 成人票
    }
}

# 日志配置
LOG_CONFIG = {
    'filename': '12306.log',
    'level': 'INFO',
    'format': '%(asctime)s - %(levelname)s - %(message)s'
}

# Cookie配置
COOKIE_CONFIG = {
    'filename': 'cookies.pkl',
    'auto_save': True  # 登录后自动保存
}
