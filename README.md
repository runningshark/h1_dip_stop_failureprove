# h1_dip_stop_failureprove

**超卖接多（带止损）** 的失败档案，属于 [量化失败合集 quant-failure-archive](https://github.com/runningshark/quant-failure-archive)。

- 结论和全部数字：[FAILURE_REPORT.md](FAILURE_REPORT.md)
- 复现：`python verify.py`（只需要 Python 3，不用装库），结果写到 `results/output.txt`
- 代码：`strategies/`（策略原文件，未改动）、`core/engine.py`（原项目回测引擎，未改动）
- 数据：`data/`，币安现货小时线快照（gzip 压缩的 JSON），截至 2026-11-23

不构成任何投资建议。
