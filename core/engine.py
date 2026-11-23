# -*- coding: utf-8 -*-
"""
通用回测 / 纸面引擎。所有策略共用这一套成交规则，所以结果可以互相比较：

  · 信号只在一根 K 线走完时判断，下一根 K 线的开盘价成交（不偷看未来）
  · 每次开仓、平仓各扣一次成本
  · 可以做多，也可以做空（做空按永续合约 1 倍计，不加杠杆；资金费没有计入）
  · 有止损价时：跳空越过止损按开盘价成交，盘中触及按止损价成交
  · 同一根 K 线里止损和止盈都碰到，按止损算（保守）
  · 出场信号和反向入场信号同时出现时：下一根开盘先平仓，再反向开仓

仓位两种算法：
  risk  每笔最多亏账户的 risk（默认 1%）→ 仓位 = risk ÷ 止损距离，上限 100%
  full  满仓（100%，不加杠杆）
"""
from .data import day, stamp


def simulate(B, sig, cost, risk, start_i, equity0, interval):
    o, h, l, c, t, done = B["o"], B["h"], B["l"], B["c"], B["t"], B["done"]
    n = len(c)
    en_l, ex_l, en_s, ex_s = sig["enter"], sig["exit"], sig.get("enter_s"), sig.get("exit_s")
    stop_dist, stop_pct, tp_pct = sig.get("stop_dist"), sig.get("stop_pct"), sig.get("tp_pct")
    max_hold, sizing = sig.get("max_hold"), sig.get("sizing", "full")
    equity, pos, pend, trades, curve = float(equity0), None, None, [], []

    def close(i, px, why):
        nonlocal equity, pos
        move = pos["dir"] * (px / pos["px"] - 1)                       # 对这笔仓位有利为正
        pos["worst"] = min(pos["worst"], move)
        frac = pos["w"] * (move - 2 * cost)                            # 占入场时账户的比例
        pnl = pos["eq0"] * frac
        equity += pnl
        trades.append(dict(side="多" if pos["dir"] > 0 else "空", entry_t=stamp(pos["t"], interval), exit_t=stamp(t[i], interval),
                           entry=pos["px"], exit=px, w=pos["w"], pct=frac, pnl=pnl,
                           r=(frac / risk if sizing == "risk" else None), bars=i - pos["i"], reason=why, worst=pos["worst"]))
        pos = None

    def hit(i):
        """检查第 i 根 K 线里止损、止盈有没有被碰到。返回 (成交价, 原因) 或 None。"""
        d, st, tp = pos["dir"], pos["stop"], pos["tp"]
        if st is not None:
            if (o[i] <= st) if d > 0 else (o[i] >= st):
                return o[i], "止损(跳空)"
            if (l[i] <= st) if d > 0 else (h[i] >= st):
                return st, "止损"
        if tp is not None and ((h[i] >= tp) if d > 0 else (l[i] <= tp)):
            return (max(o[i], tp) if d > 0 else min(o[i], tp)), "止盈"
        return None

    for i in range(start_i, n):
        if pos:
            if pos["exit_next"]:
                close(i, o[i], pos["why"])
            else:
                x = hit(i)
                if x:
                    close(i, x[0], x[1])
        if pos is None and pend is not None:
            j, d = pend
            px = o[i]
            dist = stop_dist[j] if stop_dist else (px * stop_pct if stop_pct else None)
            w = min(1.0, risk / (dist / px)) if (sizing == "risk" and dist) else 1.0
            pos = dict(i=i, t=t[i], px=px, dir=d, w=w, eq0=equity, stop=(px - d * dist) if dist else None,
                       tp=px * (1 + d * tp_pct) if tp_pct else None, exit_next=False, why="", worst=0.0)
            x = hit(i)
            if x and x[1] != "止损(跳空)":
                close(i, x[0], x[1])
        pend = None
        if pos:
            pos["worst"] = min(pos["worst"], pos["dir"] * ((l[i] if pos["dir"] > 0 else h[i]) / pos["px"] - 1))
        if done[i]:
            if pos:
                ex = ex_l[i] if pos["dir"] > 0 else (ex_s[i] if ex_s else False)
                if ex:
                    pos["exit_next"], pos["why"] = True, sig.get("exit_name", "规则出场")
                elif max_hold and i - pos["i"] + 1 >= max_hold:
                    pos["exit_next"], pos["why"] = True, "持有到期"
            if pos is None or pos["exit_next"]:
                if en_l[i] and not (pos and pos["dir"] > 0):
                    pend = (i, 1)
                elif en_s and en_s[i] and not (pos and pos["dir"] < 0):
                    pend = (i, -1)
        unreal = pos["eq0"] * pos["w"] * (pos["dir"] * (c[i] / pos["px"] - 1) - cost) if pos else 0.0
        curve.append((t[i], equity + unreal, pos["dir"] if pos else 0))
    return dict(trades=trades, curve=curve, pos=pos, pending=(pend[1] if pend else 0), equity=equity)


def simulate_weights(B, target, cost, start_i, equity0, interval, band=0.1):
    """
    按"目标仓位"运行：target[i] 是第 i 根收盘时算出的目标仓位（-1 ~ +1，负数为做空）。
    下一根开盘调仓；变化小于 band 时不动，省手续费。每一段连续同方向的持仓记成一笔交易。
    """
    o, c, t, done = B["o"], B["c"], B["t"], B["done"]
    n, equity, w, trades, curve, ep = len(c), float(equity0), 0.0, [], [], None

    def end_episode(i):
        nonlocal ep
        if ep:
            trades.append(dict(side="多" if ep["dir"] > 0 else "空", entry_t=stamp(ep["t"], interval), exit_t=stamp(t[i], interval),
                               entry=ep["px"], exit=o[i], w=ep["wsum"] / max(ep["bars"], 1), pct=equity / ep["eq0"] - 1,
                               pnl=equity - ep["eq0"], r=None, bars=i - ep["i"], reason="仓位归零或反向", worst=ep["worst"]))
            ep = None

    for i in range(start_i, n):
        if i > start_i:
            equity *= 1 + w * (o[i] / c[i - 1] - 1)                    # 隔夜（上一根收盘 → 这一根开盘）
            want = target[i - 1] if done[i - 1] and target[i - 1] is not None else w
            if abs(want - w) >= band or (want == 0 and w != 0) or (want * w < 0):
                equity -= equity * abs(want - w) * cost
                if ep and (want == 0 or want * ep["dir"] < 0):
                    end_episode(i)
                if want != 0 and ep is None:
                    ep = dict(i=i, t=t[i], px=o[i], dir=1 if want > 0 else -1, eq0=equity, wsum=0.0, bars=0, worst=0.0)
                w = want
        equity *= 1 + w * (c[i] / o[i] - 1)                            # 当根（开盘 → 收盘）
        if ep:
            ep["wsum"] += abs(w); ep["bars"] += 1
            ep["worst"] = min(ep["worst"], equity / ep["eq0"] - 1)
        curve.append((t[i], equity, (1 if w > 0 else -1 if w < 0 else 0)))
    pos = None
    if ep:
        pos = dict(i=ep["i"], t=ep["t"], px=ep["px"], dir=ep["dir"], w=abs(w), eq0=ep["eq0"], stop=None, tp=None, exit_next=False)
    last = target[-2] if (n > 1 and not done[-1]) else target[-1]
    return dict(trades=trades, curve=curve, pos=pos, pending=0, equity=equity, weight=w, target=last)


def daily_curve(curve):
    """把逐根的权益压成每天一个点（取当天最后一个）。"""
    out = {}
    for t, e, inpos in curve:
        out[day(t)] = (e, inpos)
    return [(d, v[0], v[1]) for d, v in out.items()]


def curve_stats(dc):
    """dc: [(日期, 权益, 持仓方向)]。返回 总收益 / 年化 / 夏普 / 最大回撤 / 持仓时间占比。"""
    if len(dc) < 3:
        return dict(ret=0.0, cagr=0.0, sharpe=0.0, mdd=0.0, exposure=0.0, days=len(dc))
    eq = [x[1] for x in dc]
    rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]
    mean = sum(rets) / len(rets)
    sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
    peak, mdd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        mdd = min(mdd, e / peak - 1)
    years = len(eq) / 365.0
    return dict(ret=eq[-1] / eq[0] - 1, cagr=(eq[-1] / eq[0]) ** (1 / years) - 1 if eq[-1] > 0 else -1.0,
                sharpe=mean / sd * 365 ** 0.5 if sd > 0 else 0.0, mdd=mdd,
                exposure=sum(abs(x[2]) for x in dc) / len(dc), days=len(eq))


def trade_stats(trades, years):
    n = len(trades)
    if not n:
        return dict(n=0, per_year=0.0)
    wins = [x for x in trades if x["pct"] > 0]
    losses = [x for x in trades if x["pct"] <= 0]
    has_r = trades[0]["r"] is not None
    key = "r" if has_r else "pct"
    tot = sum(x[key] for x in trades)
    best = max(x[key] for x in trades)
    top3 = sum(sorted((x["pct"] for x in trades), reverse=True)[:3])
    allp = sum(x["pct"] for x in trades)
    longs = [x for x in trades if x.get("side") == "多"]
    shorts = [x for x in trades if x.get("side") == "空"]
    return dict(n=n, per_year=n / max(years, 1e-9), win_rate=len(wins) / n, unit="R" if has_r else "%",
                avg_win=sum(x[key] for x in wins) / len(wins) if wins else 0.0,
                avg_loss=sum(x[key] for x in losses) / len(losses) if losses else 0.0,
                expectancy=tot / n, total=tot, total_ex_best=tot - best,
                worst_trade=min(x["pct"] for x in trades), worst_float=min(x["worst"] for x in trades),
                avg_bars=sum(x["bars"] for x in trades) / n, top3_share=(top3 / allp) if allp > 0 else None,
                n_long=len(longs), n_short=len(shorts), sum_long=sum(x[key] for x in longs), sum_short=sum(x[key] for x in shorts),
                win_long=(sum(1 for x in longs if x["pct"] > 0) / len(longs)) if longs else None,
                win_short=(sum(1 for x in shorts if x["pct"] > 0) / len(shorts)) if shorts else None)
