# -*- coding: utf-8 -*-
"""复现用的最小数据模块：只保留 engine.py 需要的两个时间格式函数。原项目里这个文件还负责从币安下载 K 线。"""
from datetime import datetime, timezone


def day(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def stamp(ms, interval):
    f = "%Y-%m-%d" if interval == "1d" else "%Y-%m-%d %H:%M"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(f)
