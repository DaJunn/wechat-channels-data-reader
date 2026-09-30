# wechat-channels-data-reader

让 AI 助手读取视频号单场直播数据，导出分钟趋势，并生成流量、成交与公司侧收益复盘。支持已登录后台、用户导出表和复制文本。

## 安装与依赖

```bash
git clone https://github.com/DaJunn/wechat-channels-data-reader.git \
  ~/.agents/skills/wechat-channels-data-reader
```

实时读取需要 Node.js 18+、Python 3.10+、连接正常的 Kimi WebBridge，以及已登录 `channels.weixin.qq.com` 的浏览器标签页。只分析已导出的文件无需连接后台。[Windows / Workbody 说明](references/windows-workbody-compatibility.md)。

## 快速使用

对 AI 说：“读当前视频号大屏”“11:19 的曝光、进房、在线多少”“导出每分钟趋势”“分析本场流量和成交”。

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills/wechat-channels-data-reader}"
node "$SKILL_DIR/scripts/kimi_channels_probe.mjs" --active --out ./channels_probe.json
node "$SKILL_DIR/scripts/export_live_trend_minutes.mjs" --active --out-dir ./live-trend
```

当前标签页应是目标场次的 dashboardV4。导出生成 CSV、raw JSON 和 summary JSON；分析时将实际文件路径传入：

```bash
python3 "$SKILL_DIR/scripts/analyze_live_trend_minutes.py" "<CSV文件路径>" --raw "<raw JSON文件路径>"
python3 "$SKILL_DIR/scripts/calc_channels_metrics.py" "<整理后的输入JSON路径>"
```

输入格式与完整流程见 [SKILL.md](SKILL.md)，[字段说明](references/channel-dashboard-schema.md) 和 [后台读取方法](references/kimi-webbridge-reading.md)。

## 输出与限制

- 分钟 CSV 包括曝光、进房、在线、成交金额、订单和买家；加热人次/占比保存在 JSON 中。
- 字段能否取得取决于页面实际返回。少于 10 个有效分钟点不做整场趋势判断；分钟 UV 不能直接相加为整场去重人数。
- 公司侧预估收入按佣金、分成和退款口径计算，毛利润还需公司成本。当前计算脚本缺退款率时默认 0，必须标注“退款未计入”或暂不计算，不能当作实际零退款。
- 只读取已登录页面，不代登录、不读取凭据；不靠截图补造金额和精确分钟值。探测输出的自动脱敏不能代替分享前检查。
- 趋势建议用于确定回看片段与测试动作，不直接证明流量或成交的因果。

本 skill 的趋势分析脚本也供 `wechat-channels-history-review` 使用。
