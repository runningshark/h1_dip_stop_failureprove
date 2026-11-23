# -*- coding: utf-8 -*-
"""各策略共用的小工具。"""

SHORT = dict(key="short", name="是否做空", value=0, min=0, max=1, desc="0 = 只做多；1 = 多空都做（做空规则和做多完全对称）")


def last_done(B):
    """最近一根已经走完的 K 线的下标。"""
    return len(B["c"]) - (2 if not B["done"][-1] else 1)


def point(price=None, cond="", stop=None, size=None, note=""):
    """一个方向的点位：触发价、触发条件、若触发的止损价、仓位（占账户比例）、补充说明。"""
    return dict(price=price, cond=cond, stop=stop, size=size, note=note)
