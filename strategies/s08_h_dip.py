# -*- coding: utf-8 -*-
from core.indicators import prev_high, prev_low, rsi
from ._common import SHORT, last_done, point

META = dict(
    id="s08_h_dip", name="超卖接多（带止损）", timeframe="1h", family="均值回归", verdict="反面教材", order=8,
    summary="急跌到 24 小时低点、RSI 很低时接多，赚 1% 就走，亏 2% 止损。很多带单交易员的入场方式。打开做空后，急涨到高点时反手做空。",
    logic=[("方向", "不看大方向"), ("入场", "24 小时跌超 2%，价格在 24 小时区间最低的 20%，RSI(14) 低于 35，下一小时开盘买入（做空：条件全部反过来）"),
           ("止损", "入场价反向 2%"), ("仓位", "满仓，不加杠杆"), ("出场", "赚 1% 止盈；或持满 7 天")],
    params=[dict(key="drop", name="24 小时涨跌幅 %", value=2.0, min=0.5, max=10, step=0.5, desc="做多：过去 24 小时至少跌这么多；做空：至少涨这么多"),
            dict(key="pos", name="区间位置 %", value=20, min=1, max=50, desc="做多：价格在 24 小时区间最低的这部分；做空：最高的这部分"),
            dict(key="rsi", name="RSI 界线", value=35, min=10, max=50, desc="做多：RSI 低于它；做空：RSI 高于 100 减它"),
            dict(key="tp", name="止盈 %", value=1.0, min=0.2, max=10, step=0.1, desc="赚这么多就平仓"),
            dict(key="stop", name="止损 %", value=2.0, min=0, max=20, step=0.5, desc="亏这么多就平仓；填 0 表示不止损"),
            dict(key="max_hold", name="最长持有小时数", value=168, min=1, max=1000, desc="到期不管盈亏都平仓"), SHORT],
    finding="第 5 课：胜率 64%，但每笔赚 1%、亏 2%，不计成本就已经是亏的。说明这个入场条件本身没有足够的优势。",
)


def build(B, P):
    c, n, sh = B["c"], len(B["c"]), P["short"] >= 1
    hi, lo, r = prev_high(B["h"], 24), prev_low(B["l"], 24), rsi(c, 14)
    enter, enter_s, ret24, pos24 = [False] * n, [False] * n, [0.0] * n, [0.5] * n
    for i in range(25, n):
        H, L = max(hi[i], B["h"][i]), min(lo[i], B["l"][i])          # 含当前这根的 24 小时高低
        ret24[i] = c[i] / c[i - 24] - 1
        pos24[i] = (c[i] - L) / (H - L) if H > L else 0.5
        if r[i] is None:
            continue
        enter[i] = ret24[i] < -P["drop"] / 100 and pos24[i] < P["pos"] / 100 and r[i] < P["rsi"]
        enter_s[i] = sh and ret24[i] > P["drop"] / 100 and pos24[i] > 1 - P["pos"] / 100 and r[i] > 100 - P["rsi"]
    k = last_done(B)
    st = P["stop"] / 100
    need = "24 小时涨跌 %+.1f%%，区间位置 %.0f%%，RSI %.0f" % (ret24[k] * 100, pos24[k] * 100, r[k])
    return dict(enter=enter, exit=[False] * n, enter_s=enter_s if sh else None, exit_s=[False] * n if sh else None,
                stop_pct=(st if st > 0 else None), tp_pct=P["tp"] / 100, max_hold=int(P["max_hold"]), sizing="full", warmup=30,
                points=dict(long=point(None, "三个条件同时满足", size=1.0,
                                       note="需要：24 小时跌超 %.1f%%、区间位置低于 %d%%、RSI 低于 %d。现在：%s" % (P["drop"], P["pos"], P["rsi"], need)),
                            short=point(None, "三个条件同时满足", size=1.0,
                                        note="需要：24 小时涨超 %.1f%%、区间位置高于 %d%%、RSI 高于 %d。现在：%s" % (P["drop"], 100 - P["pos"], 100 - P["rsi"], need)) if sh else None),
                levels=[("24 小时最高 / 最低", "%.2f / %.2f" % (max(B["h"][k - 23:k + 1]), min(B["l"][k - 23:k + 1]))),
                        ("止盈 / 止损", "%.1f%% / %s" % (P["tp"], ("%.1f%%" % P["stop"]) if st > 0 else "无"))])
