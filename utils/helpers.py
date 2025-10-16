#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""工具函数模块"""

import base64
import urllib.parse
from gmssl import sm4


def encrypt_password(password):
    """使用SM4加密密码"""
    try:
        key = b"tiekeyuankp12306"  # 16字节密钥
        cipher = sm4.CryptSM4()
        cipher.set_key(key, sm4.SM4_ENCRYPT)

        password_bytes = password.encode('utf-8')
        padding_length = 16 - (len(password_bytes) % 16)
        if padding_length != 16:
            password_bytes += bytes([padding_length] * padding_length)

        encrypted_blocks = []
        for i in range(0, len(password_bytes), 16):
            block = password_bytes[i:i+16]
            encrypted_block = cipher.crypt_ecb(block)[:16]
            encrypted_blocks.append(encrypted_block)

        encrypted = b''.join(encrypted_blocks)
        encrypted_b64 = '@' + base64.b64encode(encrypted).decode('utf-8')
        return encrypted_b64
    except Exception as e:
        raise Exception(f"密码加密失败: {e}")


def js_escape(s):
    """模拟JavaScript escape()函数的编码"""
    result = []
    for char in s:
        code = ord(char)
        if code < 256:
            # ASCII字符
            if char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@*_+-./':
                result.append(char)
            else:
                result.append(f'%{code:02X}')
        else:
            # Unicode字符,使用%uXXXX格式
            result.append(f'%u{code:04X}')
    return ''.join(result)


def format_seat_display(value):
    """格式化座位显示"""
    if value == '*':
        return '未开售'
    elif not value or value == '--':
        return '--'
    return value


def decode_train_info(encoded_string, station_mapping):
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
                '出发站': station_mapping.get(parts[6], parts[6]),
                '到达站': station_mapping.get(parts[7], parts[7]),
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
            raise ValueError(f"数据格式异常，字段数量: {len(parts)}")

    except Exception as e:
        raise Exception(f"解码失败: {e}")
