---
name: wechat-channels-data-reader
metadata:
  version: "1.4.4"
description: 读取视频号单场直播后台或用户导出数据，提取经营指标、分钟趋势并生成复盘。用于查询某分钟数据、导出趋势 CSV、分析流量与成交；实时读取依赖已登录页面和 Kimi WebBridge，不代登录。
---

# 微信视频号数据读取

把结构化后台数据转为可追溯的指标与运营动作。经营复盘关注公司侧预估收入和毛利润；用户只查某分钟时直接回答该分钟，不扩成整场报告。

## 输入与分流

先确认带货者、场次或时间范围，以及输入来源。支持已登录后台、CSV/Excel 和复制文本；导出表先保留原字段，再按 [字段与口径](references/channel-dashboard-schema.md) 映射。

| 需求 | 路径 |
|---|---|
| 大屏指标、商品榜、画像 | 页面接口/Network JSON、运行时 store 或 DOM 文本 |
| 某分钟数据、分钟 CSV | `export_live_trend_minutes.mjs` |
| 走势与流量承接复盘 | 分钟 CSV + raw JSON → `analyze_live_trend_minutes.py` |
| 公司侧预估收入/毛利润 | 核对字段 → `calc_channels_metrics.py` |

页面读取先读 [Kimi WebBridge 方法](references/kimi-webbridge-reading.md)；仅在 Windows、Workbody 或团队部署时读 [兼容性说明](references/windows-workbody-compatibility.md)。实时读取需 Node.js 18+、Python 3.10+、可连接的 Kimi WebBridge 和已登录视频号标签页；仅分析文件无需浏览器桥接。

## 页面指标读取

```bash
~/.kimi-webbridge/bin/kimi-webbridge status
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" --active --out ./channels_probe.json
```

核对页面账号和场次。按已返回数据提取：`dom.bodyText` 是可见文本，`network.matches` 是接口线索；接口 URL 本身不代表拿到了响应体。需监听新请求时，在监听期间切换概览/商品/画像或刷新主页面：

```bash
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" \
  --active --watch-ms 8000 --network-details --out ./channels_probe_detail.json
```

主页面空壳时读同源 `iframe[name="statistic"]` 的 store/DOM。不要直接刷新 `/micro/statistic/dashboardV4` 子页面。无结构化数据时说明缺失，不用截图 OCR 补金额或精确分钟值。

## 分钟数据与趋势

浏览器已停在目标 dashboardV4 主页面时：

```bash
node "$SKILL_DIR/scripts/export_live_trend_minutes.mjs" \
  --active --time 11:19 --out-dir ./live-trend
```

`--time` 可省略；需要指定其他已知场次时用 `--url` 传实际 dashboardV4 链接，不用示例场次 ID。URL 的 `objetctId` 与 `objectId` 均可识别。用导出的场次 ID 核对当前请求。

输出：

- `live_trend_store_<liveObjectId>.csv`：`time,ts,exposure,entry,online,transaction_amount,order_count,buyer_count`；默认北京时间，成交金额由分转元。
- `live_trend_raw_store_<liveObjectId>.json`：原始序列、概览与 `channelTraffic`。
- `live_trend_store_<liveObjectId>_summary.json`：点数、峰值、指定分钟及文件路径。

渠道加热人次和占比在 JSON 的 `channelTraffic` 中，**不是 CSV 列**。占比为加热看播 PV / 总看播 PV，不能用 UV 作分母。

```bash
python3 "$SKILL_DIR/scripts/analyze_live_trend_minutes.py" \
  "./live-trend/live_trend_store_<liveObjectId>.csv" \
  --raw "./live-trend/live_trend_raw_store_<liveObjectId>.json"
```

运行时将 `<liveObjectId>` 替换为实际 ID 并给路径加引号；脚本向终端输出 Markdown，`--json` 输出机器可读结果。可将输出保存为本次复盘文件。

分析前检查有效分钟点、缺列、空值与起止时间。少于 10 个有效点只报告数据不足。整场 UV/买家数优先取概览，不能直接相加分钟 UV 作为去重人数；分钟成交合计也需对照概览。脚本阶段与建议是启发式结果，不能仅凭峰值先后断言推荐机制、内容质量或成交原因。

趋势复盘包含：基础盘、加热人次/占比、曝光/进房/在线与成交峰值、阶段变化、待回看的时间段，以及给带货者和运营的下场动作。缺渠道字段写“未提供”，不把缺失当作自然流量或 0。

## 经营计算

先整理最小 JSON，再交给计算脚本。以下仅是字段示例，`null` 表示未提供，不能当成真实 0：

```json
{
  "talent": "带货者名称",
  "started_at": "实际开播时间",
  "source": "实际来源及采集时间",
  "gmv": null,
  "orders": null,
  "estimated_commission": null,
  "refund_rate": null,
  "mcn_share": "40%",
  "company_cost": null
}
```

```bash
python3 "$SKILL_DIR/scripts/calc_channels_metrics.py" ./input.json
```

- 客单价 = GMV / 成交订单数；预估佣金率 = 预估佣金 / GMV。
- 公司侧预估收入 = 预估佣金 × MCN 分成 × (1−退款率)。先确认佣金是否已扣退款，避免重复扣除；已净额佣金需另按其口径计算。
- 默认 MCN 分成 40%，输出明确写“默认值”。缺佣金不直接用 GMV 代替公司收入。
- **当前计算脚本把缺退款率当作 0。** 缺退款时不要把它输出的收入当作已确认净收入；应标“退款未计入的测算”或暂不计算。公司成本未提供时不填 0，毛利润写“未计算”。
- 退款率、分成先统一为明确百分数，核对范围与金额单位。详细字段约束见 [字段与口径](references/channel-dashboard-schema.md)。

## 交付与失败处理

常规复盘按“结论 → 数据来源/时间/覆盖 → 关键指标 → 证据与假设 → 下场动作”输出，金额和百分比保留 2 位小数。画像区分看播用户与买家；商品榜只读到 Top N 时标注覆盖。多场数据与跨场对比按用户范围处理。

- 页面未登录、账号/场次不符：停在登录或选择页面，由用户完成。
- store/Network/DOM 都缺数据：说明读取失败；一次合理刷新重试仍失败后保留已有结果，不编造。
- 来源口径冲突：并列原值与定义，先解释差异再判断。
- 只在已登录页面读取任务所需数据，不读取 cookies、localStorage、sessionStorage、密码或浏览器配置。探测脚本会脱敏常见键，但不保证覆盖嵌套字符串等所有情况；分享输出前仍需检查敏感信息。
- 本 skill 不发送群消息。区分已读取、已生成文件和已交付，不把建议写成已执行。
