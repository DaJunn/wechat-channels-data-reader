# 视频号直播数据字段与口径

## 核心字段

| 统一字段 | 常见中文标签 | 含义 |
|---|---|---|
| `gmv` | 累计成交金额、成交金额、GMV | 直播间成交金额，未扣退货 |
| `orders` | 成交订单数、成交单数 | 成交订单数 |
| `buyers` | 成交人数 | 下单用户数 |
| `estimated_commission` | 预估佣金 | 后台展示的佣金，未必最终结算 |
| `refund_rate` | 退款率、退货率 | 退款/退货影响比例 |
| `exposure` | 曝光 | 分钟趋势里对应 `trendingTraffic.impressionUv` |
| `entry` | 进房 | 分钟趋势里对应 `trendingTraffic.newWatchUv` |
| `online` | 在线人数 | 分钟趋势里对应 `trendingTraffic.onlineWatchUv` |
| `transaction_amount` | 成交金额 | 分钟趋势里对应 `ecConversionDashboardEcData.ecTread.gmvTread["60"]`，页面原值是分，脚本转元 |
| `order_count` | 成交订单数 | 分钟趋势里对应 `ecConversionDashboardEcData.ecTread.payPvTread["60"]` |
| `buyer_count` | 成交买家数 | 分钟趋势里对应 `ecConversionDashboardEcData.ecTread.payUvTread["60"]` |
| `heat_watch_pv` | 加热看播人次、加热流量 | 渠道流量分析里对应 `overview.promotionCumulativeWatchPv` |
| `heat_watch_pv_share` | 加热流量占比、加热占比 | `promotionCumulativeWatchPv / cumulativeWatchPv`；分子是 PV，分母也必须用看播 PV |
| `mcn_share` | MCN分成、小浪花分成 | 默认 40% |
| `company_cost` | 公司成本、投流成本、样品成本 | 公司侧承担成本 |

## 计算公式

- 客单价 = GMV / 成交订单数
- 预估佣金率 = 预估佣金 / GMV
- 公司侧收入 = 预估佣金 × MCN分成 × (1 - 退款率)
- 公司侧毛利润 = 公司侧收入 - 公司成本

默认经营参数：

- MCN 分成：40%
- 带货者分成：60%
- 平均佣金率：30%（只作对比，不可覆盖真实佣金）
- 平均退货率：20%（只作对比，不可覆盖真实退款率）

## 读数注意

- `￥2.0万` 应解析为 `20000`。
- `3.3万` 人次应解析为 `33000`，但输出可保留 `3.3万`。
- 预估佣金和最终结算佣金可能不同，必须写“预估”。
- 趋势图只有在后台给出点位数据时才可做分钟级精确读取。dashboardV4 的已验证点位数据在 `iframe[name="statistic"]` 的运行时 store：`_store.statisticStore.liveDataDashboardV4.ecConversionDashboardData.trendingTraffic`，取 `step === "60"` 且 `dimensions` 为空的序列。
- 成交金额趋势在 `ecConversionDashboardEcData.ecTread.gmvTread["60"]`；同级 `payPvTread["60"]` 是订单数，`payUvTread["60"]` 是买家数。金额原值通常以分计，输出金额必须转成元并标注口径。
- 渠道流量分析里的加热占比优先用结构化字段：`promotionCumulativeWatchPv / cumulativeWatchPv`。如果页面没有返回 `promotionCumulativeWatchPv` 或 `cumulativeWatchPv`，必须写“未提供”，不要用趋势曲线或截图估算。
- 截图/WebPlotDigitizer 只能输出 `_est` 估算字段，不能冒充后台原始分钟数据。
- 商品榜如果只读到可见 Top 项（未翻页/未抓全接口），不能说“全场商品榜”，要标注“仅 Top N”。

## 常见风险判断

- 佣金率低于 10%：除非有品牌补贴，否则公司侧空间弱。
- 退款率高于 15%：必须复盘承诺、规格、口味、适用人群和售后。
- GMV 高但平均观看短：可能靠货/平台激励，不代表内容资产强。
- 成交集中在单品：下场要验证是否可复制，别直接扩货盘。
- 新客转化低：说明平台流量没有沉淀，后续要做关注、私域或复购承接。
