# -*- coding: utf-8 -*-
"""
复现脚本：python verify.py
只用 Python 自带模块。读取 data/ 里的币安现货小时线快照，用原项目同一套回测引擎（core/engine.py）重跑：
  1. 全期（扣成本，单边 0.05%）
  2. 2024-01-01 之后（样本外：规则和参数都是在这之前定的）
  3. 纸面实盘段 2026-11-13 之后（在原项目看板上真实跑过的一段）
  4. 零成本（看亏损是不是只来自手续费）
  5. 参数敏感性（换几组参数，看有没有任何一组能翻正）
结果打印到屏幕，并写入 results/output.txt。
"""
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core.engine import simulate, daily_curve, curve_stats, trade_stats  # noqa: E402
from core.data import day  # noqa: E402
import importlib  # noqa: E402

CFG = json.load(open(os.path.join(HERE, "entry.json"), encoding="utf-8"))
MOD = importlib.import_module("strategies." + CFG["module"])
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"]
COST, RISK = 0.0005, 0.01
OOS, PAPER = "2024-01-01", "2026-11-13"


def load(sym):
    with gzip.open(os.path.join(HERE, "data", sym + "_1h.json.gz"), "rt") as f:
        B = json.load(f)
    B["done"] = [True] * len(B["c"])
    return B


def params(over=None):
    P = {p["key"]: p["value"] for p in MOD.META["params"]}
    P.update(CFG.get("params", {}))
    P.update(over or {})
    return P


def run(B, P, cost, since=None):
    sig = MOD.build(B, P)
    n = len(B["c"])
    s = sig["warmup"]
    if since:
        s = max(s, next((i for i in range(n) if day(B["t"][i]) >= since), n - 1))
    r = simulate(B, sig, cost, RISK, s, 1.0, "1h")
    dc = daily_curve(r["curve"])
    st = curve_stats(dc)
    ts = trade_stats(r["trades"], max(len(dc), 1) / 365.0)
    return st, ts, dc


def fmt(st, ts):
    if not ts.get("n"):
        return "0 笔 | – | – | – | – |"
    return "%d 笔 | 胜率 %.0f%% | 收益 %+.1f%% | 最大回撤 %.1f%% | 夏普 %.2f |" % (
        ts["n"], ts["win_rate"] * 100, st["ret"] * 100, st["mdd"] * 100, st["sharpe"])


def main():
    out = []
    P0 = params()
    out.append("# %s 复现结果\n" % MOD.META["name"])
    out.append("参数：%s；成本单边 %.2f%%；每笔风险 %.0f%%（本策略满仓、不加杠杆）\n" % (json.dumps(P0, ensure_ascii=False), COST * 100, RISK * 100))
    rows = [("全期，扣成本", COST, None), ("2024 年后（样本外），扣成本", COST, OOS),
            ("纸面实盘段 2026-11-13 起，扣成本", COST, PAPER), ("全期，零成本", 0.0, None), ("2024 年后，零成本", 0.0, OOS)]
    for sym in SYMBOLS:
        B = load(sym)
        out.append("\n## %s（%s 至 %s，共 %d 根小时线）\n" % (sym, day(B["t"][0]), day(B["t"][-1]), len(B["c"])))
        out.append("| 段 | 笔数 | 胜率 | 收益 | 最大回撤 | 夏普 |\n|---|---|---|---|---|---|")
        for name, cost, since in rows:
            st, ts, _ = run(B, P0, cost, since)
            out.append("| %s | %s" % (name, fmt(st, ts)))
    out.append("\n## 参数敏感性（BTCUSDT、ETHUSDT，全期扣成本 / 2024 年后扣成本）\n")
    out.append("| 参数 | BTC 全期 | BTC 2024 后 | ETH 全期 | ETH 2024 后 |\n|---|---|---|---|---|")
    data = {s: load(s) for s in ("BTCUSDT", "ETHUSDT")}
    for over in CFG.get("grid", []):
        cells = []
        for s in ("BTCUSDT", "ETHUSDT"):
            for since in (None, OOS):
                st, ts, _ = run(data[s], params(over), COST, since)
                cells.append("%+.0f%%" % (st["ret"] * 100))
        out.append("| %s | %s |" % (json.dumps(over, ensure_ascii=False), " | ".join(cells)))
    text = "\n".join(out) + "\n"
    print(text)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "output.txt"), "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
