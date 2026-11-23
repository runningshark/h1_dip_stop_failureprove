# -*- coding: utf-8 -*-
"""指标：全部只用"当前这根及以前"的数据。数据不够的位置返回 None。"""
from collections import deque


def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def _roll(x, n, better):
    """前 n 根（不含当前）的最大/最小值，单调队列实现。"""
    out, q = [None] * len(x), deque()
    for i, v in enumerate(x):
        if i >= n:
            out[i] = x[q[0]]
        while q and better(v, x[q[-1]]):
            q.pop()
        q.append(i)
        while q[0] <= i - n:
            q.popleft()
    return out


def prev_high(x, n):
    return _roll(x, n, lambda a, b: a >= b)


def prev_low(x, n):
    return _roll(x, n, lambda a, b: a <= b)


def atr(h, l, c, n):
    tr = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) if i else h[i] - l[i] for i in range(len(c))]
    return sma(tr, n)


def rsi(c, n=14):
    out, up, dn = [None] * len(c), 0.0, 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        up += (max(d, 0.0) - up) / n
        dn += (max(-d, 0.0) - dn) / n
        if i >= n:
            out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


def stdev(x, n):
    out, s, s2 = [None] * len(x), 0.0, 0.0
    for i, v in enumerate(x):
        s += v; s2 += v * v
        if i >= n:
            s -= x[i - n]; s2 -= x[i - n] ** 2
        if i >= n - 1:
            var = max(0.0, s2 / n - (s / n) ** 2)
            out[i] = var ** 0.5
    return out
