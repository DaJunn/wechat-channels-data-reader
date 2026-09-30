# wechat-channels-data-reader

**视频号直播数据读取** —— 把已登录后台里的直播数据读成结构化表格，不截图、不 OCR、不编数字。

让 AI agent（DSH / Codex / Claude Code 等）使用。

## 解决什么问题

之前看视频号直播数据得一个 tab 一个 tab 翻着手抄，canvas 数据大屏连复制都复制不了。

现在能把数据读成结构化 JSON / CSV。

## 能读什么

GMV、成交金额、成交单量、预估佣金、退货率、观看转化、用户画像、商品榜，以及**分钟级趋势**（每分钟曝光 / 进房 / 在线 / 成交金额 / 订单数 / 买家数），可导出 CSV 做趋势分析。

## 读取路径（按优先级）

1. **页面接口 / Network JSON** —— canvas 数据大屏只能走这条
2. **DOM 可见文本** —— order-list 等文本型页面直读 innerText
3. **用户提供的 CSV / Excel** —— 按原字段映射，不补不存在的字段

读不到就报「读取失败，请切 tab / 刷新后重试」，**绝不用截图凑数**。

## 前置依赖

1. **kimi-webbridge daemon** 在跑：
   ```bash
   ~/.kimi-webbridge/bin/kimi-webbridge status   # 要 running:true + extension_connected:true
   ```
   没装：`curl -fsSL https://cdn.kimi.com/webbridge/install.sh | bash`
2. **Chrome 已登录** `channels.weixin.qq.com`。本 skill 只复用你自己已打开的标签页，**不代登录、不绕过登录**。
3. Node.js（探测与导出脚本）、Python 3（计算脚本）

## 安装

```bash
git clone https://github.com/DaJunn/wechat-channels-data-reader.git \
  ~/.agents/skills/wechat-channels-data-reader
```

## 脚本

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"

# 探测当前页面，自动脱敏 cookie/token
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" --active --out ./channels_probe.json

# 抓最新接口（先开监听，再让用户切 tab 或刷新）
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" --active --network-details --out ./channels_probe_detail.json

# 导出分钟趋势 CSV
node "$SKILL_DIR/scripts/export_live_trend_minutes.mjs"

# 趋势分析
python3 "$SKILL_DIR/scripts/analyze_live_trend_minutes.py" [csv] --raw [raw-json]

# 公司侧收入 / 毛利计算
python3 "$SKILL_DIR/scripts/calc_channels_metrics.py" /path/to/input.json
```

## 触发方式

对 agent 说：「读一下当前视频号大屏」「11:19 的曝光/进房/在线多少」「导出每分钟趋势 CSV」「描述本场走势」「这场流量怎么样」。

## 目录

```
SKILL.md                                    agent 读的主文件
agents/openai.yaml                          UI 元数据
references/channel-dashboard-schema.md      字段表与计算口径
references/kimi-webbridge-reading.md        已登录页面读取方法
references/windows-workbody-compatibility.md 跨平台说明
scripts/                                    探测 / 导出 / 分析 / 计算
test-prompts.json                           测试用例
```

## 安全

- 脚本会**自动脱敏** `cookie`、`authorization`、`token`、`secret`，不会写进回复、笔记或仓库
- 只用你自己浏览器的登录态，不代登录

## 默认口径

- 公司侧收入 = 预估佣金 × MCN 分成 × (1 − 退款率)
- 默认 MCN 分成 40%
- 优先用后台的「预估佣金」实际值，不要用 GMV × 默认佣金率硬算
- 缺字段写「未提供」，不编造

## 也是底座

`wechat-channels-history-review` 依赖本 skill 的分钟趋势与趋势分析脚本。
