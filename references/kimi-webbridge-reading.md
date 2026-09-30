# Kimi WebBridge 读取视频号数据大屏

## 目标

用结构化的 DOM 文本和 Network 接口 JSON 读取已登录视频号数据大屏，**不截图、不做视觉 OCR**（后台是金额/经营口径，视觉读数容易错）。

读取优先级（不截图）：

1. Network / 页面接口 JSON（canvas 数据大屏只能走这条）
2. dashboardV4 iframe 运行时 store（分钟趋势图常在这里）
3. DOM 可见文本（order-list 等文本型页面）

两者都拿不到时：切 tab / 刷新后用 `--watch-ms` + `--network-details` 重跑；仍无则报“读取失败”，不要退回截图。

## 必做安全边界

- 只复用用户已经打开的 `channels.weixin.qq.com` 页面。
- 不代登录、不扫码、不保存登录态。
- 不读取或输出 cookie、authorization、token、secret、localStorage、sessionStorage。
- 不点击“导出”“提交”“删除”“保存”等会改变后台状态的按钮，除非用户明确要求并在动作前确认。
- 页面接口只作为本次复盘数据源，不沉淀敏感原始响应到公开目录。

## 标准探测命令

```bash
~/.kimi-webbridge/bin/kimi-webbridge status

SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" \
  --active \
  --out ./channels_probe.json
```

如果页面已经打开但不是当前页，可去掉 `--active`：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" \
  --out ./channels_probe.json
```

需要抓 Network 详情时：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" \
  --active \
  --network-details \
  --out ./channels_probe_detail.json
```

如果 Network 为空，让用户在浏览器里切换“概览/商品/画像”或刷新页面，同时监听 8 秒：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" \
  --active \
  --watch-ms 8000 \
  --network-details \
  --out ./channels_probe_detail.json
```

## 读结果

`dom.bodyText`：

- 脚本已内置**渲染等待**（轮询 innerText 直到稳定），异步 SPA 页面无需手动 sleep。
- 如果包含“累计成交金额 / 成交订单数 / 用户特征 / 性别分布 / 年龄分布”等可见文本，直接提取。
- 如果 bodyText 仍很短，说明是 canvas 或虚拟渲染（如 dashboardV4 概览/商品 tab），转看 Network；order-list 这类文本页则应能拿到完整表格文本。

`performance.likelyApiUrls`：

- 来自页面 `performance.getEntriesByType("resource")`。
- 用来发现可能的数据接口，不代表已经拿到响应体。

`network.matches`：

- 来自 Kimi WebBridge network list。
- 优先筛关键词：`statistic`, `dashboard`, `profile`, `portrait`, `audience`, `buyer`, `fan`, `goods`, `product`, `live`。

`network.details`：

- 仅在 `--network-details` 时输出。
- 看 response/body/data 里有没有 JSON 指标。
- 若只有空列表，提示用户在页面上切换“概览/商品/画像”或刷新，再重跑。

## dashboardV4 分钟趋势

用户问“某一分钟曝光/进房/在线是多少”时，先跑：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/export_live_trend_minutes.mjs" \
  --url "<channels dashboardV4 url>" \
  --time 11:19
```

已验证结构：

- 主页面 `document.body.innerText` 可能为空或只有外壳。
- 真实数据在同源 `iframe[name="statistic"]`。
- 运行时路径：`iframe.contentWindow._store.statisticStore.liveDataDashboardV4.ecConversionDashboardData.trendingTraffic`。
- 分钟级点位取 `step === "60"` 且 `dimensions` 为空的序列。
- `impressionUv` = 曝光，`newWatchUv` = 进房，`onlineWatchUv` = 在线人数。
- 成交分钟点位在 `iframe.contentWindow._store.statisticStore.liveDataDashboardV4.ecConversionDashboardEcData.ecTread`：
  - `gmvTread["60"]` = 成交金额，页面原值是分，脚本转成元。
  - `payPvTread["60"]` = 成交订单数。
  - `payUvTread["60"]` = 成交买家数。
- 渠道流量/加热占比在 `iframe.contentWindow._store.statisticStore.liveDataDashboardV4.ecConversionDashboardData.overview`：
  - `promotionCumulativeWatchPv` = 加热看播人次。
  - `cumulativeWatchPv` = 总看播人次。
  - 加热流量占比 = `promotionCumulativeWatchPv / cumulativeWatchPv`。
- 不要直接打开或刷新 iframe 的 `/micro/statistic/dashboardV4...` 地址；要刷新主 dashboardV4 页面。

脚本只保存趋势数组和基础直播信息，不读取 cookie、localStorage、sessionStorage、密码或请求头。

## 画像字段

画像页常见分层：

- `audience_all` / 整场看播用户
- `audience_fans` / 整场看播粉丝
- `buyers_all` / 整场买家-全部
- `buyers_new` / 整场买家-新客
- `buyers_old` / 整场买家-老客

每个分层尽量读取：

- 样本人数
- 性别分布
- 年龄分布
- 省份 / 城市
- 购买偏好
- 人群属性
- 消费力区间
- 粉丝占比 / 买过观众占比（若有）

输出时要区分“看播画像”和“买家画像”。不要把看播用户画像误说成成交买家画像。

## 业务解释

- 看播画像决定内容和开场钩子。
- 买家画像决定货盘和成交话术。
- 新客画像决定平台推荐成交人群。
- 老客画像样本量小于 30 时，只能做参考，不要下结论。
- 若买家集中在 59 岁以上、0-99 元、食品饮料/保健相关偏好，下场应强化“早餐/日常食用/真实场景/规格口味解释”，避免夸大功效。
