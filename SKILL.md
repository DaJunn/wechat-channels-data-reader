---
name: wechat-channels-data-reader
metadata:
  version: "1.4.4"
description: 读取和复盘微信视频号直播数据。优先通过 Kimi WebBridge 在用户已登录的 channels.weixin.qq.com 页面，按 DOM、Network JSON 或 dashboardV4 iframe 运行时 store 抽取结构化数据（不截图、不 OCR）；也支持 CSV/Excel 导出或复制文本。用于 GMV、成交金额、成交单量、预估佣金、退货率、观看/转化/画像/商品榜复盘，以及用户问“10:47曝光/进房/在线多少”“导出每分钟趋势 CSV”“直播趋势图每分钟数据”“趋势分析”“描述本场走势”“这场有成交”时导出和分析分钟级曝光、进房、在线、成交金额、订单数、买家数、渠道流量分析、加热流量占比、给带货者建议、给运营建议。不代登录、不绕过 channels.weixin.qq.com 后台访问限制。
---

# 微信视频号数据读取

用于把视频号直播后台的已登录页面（DOM 文本 / Network JSON）、导出表或复制文本转成小浪花可执行的经营复盘。**不用截图、不做视觉 OCR**——后台数字是金额和经营口径，必须取自页面结构化数据。北极星不是 GMV，而是公司侧可确认收入和毛利润。

## 快速流程

1. 识别输入类型：
   - 用户问“某一分钟曝光/进房/在线/成交是多少”或“导出每分钟趋势 CSV”：直接走“分钟趋势读取路径”。
   - 用户问“趋势分析”“描述本场走势”“这场流量怎么样”：先走“分钟趋势读取路径”导出 CSV，再走“趋势分析路径”。
   - Kimi WebBridge 已登录页面（默认、首选）：走“页面/API 读取路径”，按 DOM 文本 / Network JSON 抽取，不截图。
   - CSV/Excel 导出：读取表头和字段，先保留原始字段，再做字段映射。
   - 复制文本：按可见标签提取，不补不存在的字段。
2. 读取 `references/channel-dashboard-schema.md`，按字段表和公式统一口径；如要操作已登录页面，再读 `references/kimi-webbridge-reading.md`。
   - 如果用户问 Windows、Workbody、团队安装、跨平台可用性，先读 `references/windows-workbody-compatibility.md`。
3. 按优先级读取数据（不截图）：
   1. 页面接口/Network JSON（canvas 数据大屏只能走这条）
   2. DOM 可见文本（order-list 等文本型页面直读 innerText）
   - 两者都拿不到 → 报“读取失败，请切 tab/刷新后重试”，不要截图凑数。
4. 生成一个最小 JSON，交给脚本计算：
   ```bash
   SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
   python3 "$SKILL_DIR/scripts/calc_channels_metrics.py" /path/to/input.json
   ```
5. 输出复盘：
   - 先给结论：公司侧收入/毛利、是否值得复盘放大。
   - 再给关键指标、商品榜、用户画像、风险、下一步动作。
   - 明确数据来源（DOM / Network / 导出文件）、采集时间、字段缺失。

🔴 STOP：当用户要“精确分钟数据/趋势分析”但页面 store、Network JSON、CSV/Excel 都不可用时，停止并说明缺少结构化数据；不要用截图补造精确分钟数。

## 页面/API 读取路径

当用户说“Codex 用 Kimi WebBridge 登录了”“读取当前视频号大屏”“看已打开的 channels 页面”时：

1. 先做 Kimi WebBridge 健康检查：
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status
   ```
2. 只复用用户已经打开、已登录的 `channels.weixin.qq.com` 标签页；不要代登录、不要绕过登录。
3. 先跑探测脚本：
   ```bash
   SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
   node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" --active --out ./channels_probe.json
   ```
4. 查看 `./channels_probe.json`：
   - `dom.bodyText` 有完整指标：按 DOM 文本提取。
   - `network.matches` 有 `statistic/dashboard/profile/portrait/audience/buyer/fan` 等接口：优先看接口结构。
   - 两者都缺：让用户在浏览器里切换“概览/商品/画像”tab 或刷新，再用 `--watch-ms 8000 --network-details` 重跑抓接口；仍拿不到就报“读取失败”，不要截图。
5. 如果要抓最新接口，先开启监听，让用户切换“概览/商品/画像”或刷新页面，再列请求：
   ```bash
   SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
   node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" --active --network-details --out ./channels_probe_detail.json
   ```

脚本会脱敏 `cookie`、`authorization`、`token`、`secret` 等字段。不要把这些敏感字段写进回复、笔记或仓库。

## Windows / Workbody 兼容性

本 Skill 的脚本不依赖 macOS 专属 API；核心要求是运行环境能执行 Node.js 18+、Python 3，并能访问本机 Kimi WebBridge 的 `KIMI_WEBBRIDGE_URL`。Windows 和 Workbody 场景按 `references/windows-workbody-compatibility.md` 判断：

- Windows：可用 PowerShell 路径安装；Python 命令可能是 `python` 而不是 `python3`。
- Workbody：如果能运行本地 Node/Python 并连接已登录浏览器或 Kimi WebBridge，则可读实时页面；如果只能上传文件，则只能分析 CSV/raw，不能精确读取已登录后台。
- 发布给团队前必须保留“只读已登录页面、不读 cookie/token、不截图 OCR 金额”的限制说明。

## 分钟趋势读取路径

当用户问“10:47 / 11:19 的曝光、进房、在线是多少”“每一分钟趋势导出”“把趋势图读成 CSV”时，优先读 dashboardV4 iframe 的运行时 store。不要用截图或 WebPlotDigitizer 估算，除非页面 store 不可用且用户明确接受估算。

标准命令：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/export_live_trend_minutes.mjs" \
  --url "https://channels.weixin.qq.com/platform/statistic/dashboardV4?objetctId=14952183255037381180&entrance_id=3" \
  --time 11:19
```

输出文件默认在 `~/outputs/live-trend-digitized/`：

- `live_trend_store_<liveObjectId>.csv`
- `live_trend_raw_store_<liveObjectId>.json`
- `live_trend_store_<liveObjectId>_summary.json`

CSV 固定列：

- `time`: 分钟时间，按北京时间显示。
- `ts`: 后台点位时间戳。
- `exposure`: 曝光，来自 `trendingTraffic.impressionUv` 的 `step === "60"` 无维度序列。
- `entry`: 进房，来自 `trendingTraffic.newWatchUv` 的 `step === "60"` 无维度序列。
- `online`: 在线人数，来自 `trendingTraffic.onlineWatchUv` 的 `step === "60"` 无维度序列。
- `transaction_amount`: 成交金额，来自 `ecConversionDashboardEcData.ecTread.gmvTread["60"]`；页面原值是分，脚本转成元。
- `order_count`: 成交订单数，来自 `ecConversionDashboardEcData.ecTread.payPvTread["60"]`。
- `buyer_count`: 成交买家数，来自 `ecConversionDashboardEcData.ecTread.payUvTread["60"]`。
- `channelTraffic.heat_watch_pv`: 加热看播人次，来自 `overview.promotionCumulativeWatchPv`。
- `channelTraffic.heat_watch_pv_share`: 加热流量占比，按 `promotionCumulativeWatchPv / cumulativeWatchPv` 计算；因为加热字段是 PV，人次占比分母必须用看播人次 PV，不用 UV。

已验证的 dashboardV4 结构：

- 主页面 DOM 可能只是空壳，真实数据在同源 `iframe[name="statistic"]`。
- 不要直接刷新 iframe 的 `/micro/statistic/dashboardV4...` 地址；必要时刷新主页面。
- 运行时路径：`iframe.contentWindow._store.statisticStore.liveDataDashboardV4.ecConversionDashboardData.trendingTraffic`。
- 成交趋势路径：`iframe.contentWindow._store.statisticStore.liveDataDashboardV4.ecConversionDashboardEcData.ecTread`。
- 渠道流量/加热口径路径：`iframe.contentWindow._store.statisticStore.liveDataDashboardV4.ecConversionDashboardData.overview.promotionCumulativeWatchPv`；总看播人次是同级 `cumulativeWatchPv`。
- URL 参数可能写作 `objetctId`，脚本同时兼容 `objectId`。

读取失败时：

- 如果脚本提示 `dashboard runtime store is unavailable`，让用户确认浏览器停在已登录 dashboardV4 主页面，并刷新主页面后重跑。
- 如果缺 `impressionUv/newWatchUv/onlineWatchUv` 分钟序列，停止并说明后台当前没有给出分钟趋势数组，不要补造。
- 下载的 HTML 通常只保留当前 tooltip 点位，不能精确还原整条趋势；只能当作辅助证据。

## 趋势分析路径

当用户问“趋势分析”“本场情况”“流量走势”“进房/在线承接怎么样”时，先确保已有分钟 CSV；没有就先跑分钟趋势脚本。再运行：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
python3 "$SKILL_DIR/scripts/analyze_live_trend_minutes.py" \
  "$HOME/outputs/live-trend-digitized/live_trend_store_<liveObjectId>.csv" \
  --raw "$HOME/outputs/live-trend-digitized/live_trend_raw_store_<liveObjectId>.json"
```

趋势分析固定输出：

- 数据口径：CSV/raw 路径、直播对象、起止时间、分钟点数、缺失字段。
- 整场基础盘：曝光 UV、看播 UV、曝光到看播率、平均在线、峰值在线、平均观看时长、互动/关注。
- 渠道流量：每次趋势分析必须输出加热看播人次、加热流量占比；如果字段缺失写“未提供”，不要用截图估算。
- 关键峰值：曝光峰值、进房峰值、在线峰值，以及三者是否错位。
- 成交指标：如果 CSV 有 `transaction_amount/order_count/buyer_count`，输出成交金额、订单、买家、成交峰值、单进房成交额、千次曝光成交额。
- 阶段拆解：开场、平台放量、高在线承接、回落维持、尾段稳定，每段给平均曝光、进房、在线、进房率。
- 复盘判断：用“平台给量 / 点击进房 / 在线留存 / 后续动作”四句话落到运营动作。
- 建议输出：每次趋势分析最后必须增加“给带货者建议”和“给运营建议”。给带货者建议偏话术、节奏、互动、转化动作；给运营建议偏回看片段、数据补齐、加热/自然流量拆分、下场测试设计。

判断规则：

- 曝光峰值早于在线峰值 5 分钟以上：写“平台先给量，内容承接滞后变好”。
- 高曝光窗口进房率低于后段进房率：写“前段推荐流量浪费，标题/封面/开场钩子要优化”。
- 在线峰值出现在曝光回落后：写“内容留人能力比点击吸引更强，复盘该时间段话题/货品/互动”。
- 尾段在线维持但进房下滑：写“老观众还在，新流量衰减，尾段适合转成交/关注，不适合重新起流量”。
- 成交只集中在尾段：写“成交动作发生在尾段，需回看成交分钟前后 5 分钟的话术、商品展示和逼单动作”。

🔴 STOP：如果 CSV 少于 10 个有效分钟点，停止趋势判断，只输出“数据不足”和缺失原因。不要把 1-2 个 tooltip 点位当成整场趋势。

## 输入 JSON

脚本只做经营计算，不负责 OCR。先把读到的字段整理成：

```json
{
  "talent": "加拿大薇薇",
  "live_title": "放弃2000㎡实体店来加拿大...",
  "started_at": "2026-05-30 21:00",
  "source": "页面DOM/Network",
  "gmv": "¥20,421.50",
  "orders": 179,
  "estimated_commission": "3432.28",
  "refund_rate": "17.32%",
  "mcn_share": "40%",
  "company_cost": 0
}
```

字段名也可用中文同义词：`累计成交金额`、`成交订单数`、`预估佣金`、`退款率`、`MCN分成`、`公司成本`。

## 输出要求

每次使用本 Skill 后，最后必须追加一个“简版同步”，3-5 行即可，让用户快速知道：

- 本次用了哪个数据源/脚本。
- 读到了什么关键结果。
- 有什么缺失或风险。
- 下一步最该看哪一个片段或指标。

固定用这个结构：

```text
结论：
【一句话说明这场值不值得继续放大，以及公司侧收入/毛利】

数据口径：
- 来源：
- 采集时间：
- 提取方式：
- 缺失字段：

核心指标：
- GMV：
- 成交单量：
- 客单价：
- 预估佣金：
- 预估佣金率：
- 退款率：
- 公司侧收入：
- 公司侧毛利润：

判断：
1. 【内容/流量判断】
2. 【货盘/转化判断】
3. 【带货者/人群判断】

风险：
- 【退货、佣金率、客诉、合规或数据缺失风险】

下一步：
1. 【复盘动作】
2. 【下场测试动作】
3. 【数据补齐动作】
```

如果用户问的是趋势分析而不是经营复盘，输出改为：

```text
结论：
【一句话判断本场流量节奏和承接问题】

数据口径：
- 来源：
- 场次：
- 时间：
- 分钟点：

整场基础盘：
- 曝光 UV：
- 看播 UV：
- 曝光到看播：
- 平均在线 / 峰值在线：
- 平均观看：
- 加热看播人次 / 占比：
- 成交金额 / 订单 / 买家：
- 单进房成交额：
- 千次曝光成交额：

趋势拆解：
1. 【开场】
2. 【平台放量】
3. 【承接最好】
4. 【回落维持】
5. 【尾段】

关键时间点：
- 曝光峰值：
- 进房峰值：
- 在线峰值：
- 成交峰值：

判断：
1. 【平台给量】
2. 【点击进房】
3. 【在线留存】

下一步：
1. 【回看片段】
2. 【下场测试】

给带货者建议：
1. 【话术/钩子/节奏建议】
2. 【互动/留人/转化建议】

给运营建议：
1. 【回看与标注建议】
2. 【数据补齐与下场测试建议】
```

## 规则

- 不代登录、不绕过 `channels.weixin.qq.com` 后台限制；只复用用户已登录的页面读 DOM/Network，或用户提供的导出文件/可复制文本。
- 用 Kimi WebBridge 时，只在已登录页面上下文读取 DOM/Network/页面接口；禁止读取 cookies、localStorage、sessionStorage、密码或浏览器配置文件。
- 接口字段必须来自页面实际返回；不要编造 endpoint、字段名或请求参数。
- 数字一律取自 DOM 文本 / Network JSON / 导出文件；不靠截图视觉读数，避免金额误读。
- 分钟趋势图优先用 dashboardV4 运行时 store；只有 store 不可用且用户明确要求估算时，才可说明“截图估算”并单独输出 `_est` 字段。
- 不编造飞书字段、后台字段或商品数据。缺字段就写“未提供”。
- 所有金额保留 2 位小数；百分比保留 2 位。
- 默认 MCN 分成 40%，默认只在用户没提供时使用；输出里必须标注“默认值”。
- 默认经营公式：公司侧收入 = 预估佣金 × MCN分成 × (1 - 退款率)。
- 若提供公司成本：公司侧毛利润 = 公司侧收入 - 公司成本；否则毛利润写“未计算（缺公司成本）”。
- 主动提醒：GMV 高但佣金率低、退款率高、投流成本未计入，都不能直接判定赚钱。

## 可选深挖

当页面包含趋势图、商品成交榜或画像时，补充：

- 成交峰值时间段：读趋势图的成交金额尖峰，指出对应复盘片段。
- 商品榜：列 Top SKU、GMV/佣金贡献、是否过度依赖单品。
- 用户画像：地区、年龄、性别、价格带，用来推下场货盘和话术。
- 内容力：平均观看时长、点击率、评论率、直播有效进房率。

只有在用户要求生成日报/周报时，才把多场数据汇总成表格；单场复盘保持短。

## 默认口径

- 数据源优先级：Network JSON > DOM 可见文本 > 用户导出 CSV/Excel > 复制文本。
- 统一称「带货者」，不写「主播」。
- 北极星是公司侧收入和毛利润；GMV 只是上游指标。
- 缺佣金率、退款率、公司成本时，必须标注未提供或默认值。

## 工作流

1. 判断输入类型：已登录页面、导出文件、复制文本。
2. 需要读已登录页面时，先读 `references/kimi-webbridge-reading.md`。
3. 需要字段口径时，读 `references/channel-dashboard-schema.md`。
4. 抽取最小 JSON，再用脚本计算指标。
5. 输出复盘：结果、公司侧收入、风险、下一步动作。

## 失败处理

- 🔴 STOP 页面没登录或不是视频号后台：提示用户切到正确页面，不代登录。
- 🔴 STOP Network/DOM/store 都拿不到：停止并说明读取失败，不截图 OCR。
- 🔴 STOP 分钟 CSV 少于 10 个有效点：只报告数据不足，不输出阶段判断。
- 🔴 STOP 导出表缺字段：列缺失字段，不编造。
- GMV、佣金、退款率口径冲突：保留原始来源并标注差异。

## 禁止做什么

- 不截图 OCR 金额。
- 不读取 Cookie、localStorage、密码或浏览器配置。
- 不编造接口、字段、带货者数据或商品数据。
- 不把 GMV 当公司收入或毛利润。

## 验证清单

- 输入来源明确。
- 字段映射可追溯。
- 公式和默认值已标注。
- 输出不含隐私和登录态信息。
