# 视频号直播数据字段与口径

## 经营字段

| 统一字段 | 常见标签 | 说明 |
|---|---|---|
| `gmv` | 累计成交金额、成交金额、GMV | 直播成交金额；核对退款是否已扣及金额单位 |
| `orders` | 成交订单数、成交单数 | 订单数，不能代替件数或买家数 |
| `estimated_commission` | 预估佣金 | 后台预估值，不等于最终结算；核对是否已扣退款 |
| `refund_rate` | 退款率、退货率 | 核对金额/订单比例、统计窗口；不同口径不可直接替换 |
| `mcn_share` | MCN分成、小浪花分成 | 未提供时可用 40%，须标默认值 |
| `company_cost` | 公司成本、投流成本、成本 | 应为公司承担成本合计；单项投流成本不足以代表全部成本 |

`calc_channels_metrics.py` 支持上表别名。“样品成本”等其他明细需先汇总映射到 `company_cost`，不是自动识别的别名。缺成本保留 `null`，不要填 0；示例参数不能当作实测数据。

计算：客单价 = GMV / 订单；预估佣金率 = 预估佣金 / GMV。公司侧预估收入 = 预估佣金 × MCN 分成 × (1−退款率)，仅适用于佣金未扣退款且退款口径可比的情形；净额佣金不重复扣退。毛利润还需扣公司成本。

**当前脚本限制：** 缺退款率会按 0 计算，不能据此报告真实 0 退款或确认净收入。缺退款时明确“退款未计入的测算”或不输出收益判断。脚本不验证比例范围；输入前核对分成/退款为 0–100%，以 `"1%"` 这类明确百分数传入，避免数值 `1` 被解释为 100%。

金额字符串支持千分位与“万”；仍需核对负数、货币和元/分。平均佣金率 30%、退货率 20% 仅作显式假设，不能覆盖后台实际值。

## 分钟 CSV 与 JSON

CSV 字段固定为：

| 字段 | 后台来源 |
|---|---|
| `time` / `ts` | 默认北京时间 `HH:MM` / 秒级时间戳 |
| `exposure` | `trendingTraffic.impressionUv` |
| `entry` | `trendingTraffic.newWatchUv` |
| `online` | `trendingTraffic.onlineWatchUv` |
| `transaction_amount` | `ecTread.gmvTread["60"]`，分转元 |
| `order_count` | `ecTread.payPvTread["60"]` |
| `buyer_count` | `ecTread.payUvTread["60"]` |

`trendingTraffic` 位于同源 statistic iframe 的 `_store.statisticStore.liveDataDashboardV4.ecConversionDashboardData`；`ecTread` 位于同级 `ecConversionDashboardEcData`。读取 60 秒无维度序列；脚本会回退到其他 60 秒序列，回退时应核对维度，不能混为整场。

加热数据位于 raw/summary JSON 的 `channelTraffic`：

- `heat_watch_pv` = `overview.promotionCumulativeWatchPv`。
- `heat_watch_pv_share` = 加热看播 PV / `overview.cumulativeWatchPv`，分子分母均为人次。
- 缺字段或分母为 0 时不可判定占比；缺失不能等同于没有加热。

分钟序列存在空字段时脚本部分合计仍显示 0，先检查原始序列是否实际提供。分钟 UV、买家数之和不等于整场去重人数；以概览去重字段为准。跨午夜或多日直播定位分钟时同时核对 `ts` 与日期，不能只看 `HH:MM`。

## 解读边界

- 商品榜仅覆盖可见 Top N 时需标注；看播画像与买家画像分开。
- 预估佣金、成交、退款的采集时间不同会产生差异，保留原值和来源。
- GMV 高不代表公司毛利润高，需结合佣金、退款和成本。
- 低佣金、高退款或单品集中用于提示复查；阈值结合品类与历史基线，不自动断言盈亏或原因。
- 只有结构化点位足够才做精确趋势；用户明确接受的视觉估算要单列 `_est`，不得混入后台实测数据。
