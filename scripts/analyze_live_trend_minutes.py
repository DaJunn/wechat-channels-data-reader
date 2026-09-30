#!/usr/bin/env python3
"""Analyze WeChat Channels minute-level live trend CSV.

Input CSV columns must include: time, exposure, entry, online.
Optional raw JSON can provide live metadata and overview fields exported by
export_live_trend_minutes.mjs.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from typing import Any


CN_TZ = timezone(timedelta(hours=8))


@dataclass
class Row:
    time: str
    ts: int | None
    exposure: int
    entry: int
    online: int
    transaction_amount: float | None = None
    order_count: int = 0
    buyer_count: int = 0

    @property
    def entry_rate(self) -> float | None:
        if self.exposure <= 0:
            return None
        return self.entry / self.exposure


def to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(str(value).replace(",", "")))


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def read_rows(csv_path: Path) -> list[Row]:
    rows: list[Row] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"time", "exposure", "entry", "online"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SystemExit(f"CSV missing required column(s): {', '.join(missing)}")
        for raw in reader:
            rows.append(
                Row(
                    time=str(raw.get("time") or ""),
                    ts=to_int(raw.get("ts")) if raw.get("ts") else None,
                    exposure=to_int(raw.get("exposure")),
                    entry=to_int(raw.get("entry")),
                    online=to_int(raw.get("online")),
                    transaction_amount=to_float(raw.get("transaction_amount")),
                    order_count=to_int(raw.get("order_count")),
                    buyer_count=to_int(raw.get("buyer_count")),
                )
            )
    return [r for r in rows if r.time]


def read_raw(raw_path: Path | None) -> dict[str, Any]:
    if not raw_path:
        return {}
    if not raw_path.exists():
        raise SystemExit(f"raw JSON not found: {raw_path}")
    return json.loads(raw_path.read_text(encoding="utf-8"))


def metric_int(overview: dict[str, Any], key: str) -> int | None:
    value = overview.get(key)
    if value in (None, ""):
        return None
    return to_int(value)


def ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def channel_traffic(raw: dict[str, Any]) -> dict[str, Any]:
    existing = raw.get("channelTraffic")
    if isinstance(existing, dict) and existing:
        return existing
    overview = raw.get("overview") or {}
    total_watch_pv = metric_int(overview, "cumulativeWatchPv")
    heat_watch_pv = metric_int(overview, "promotionCumulativeWatchPv")
    ads_watch_pv = metric_int(overview, "adsCumulativeWatchPv")
    return {
        "source": "ecConversionDashboardData.overview",
        "total_watch_pv": total_watch_pv,
        "total_watch_uv": metric_int(overview, "cumulativeWatchUv"),
        "heat_watch_pv": heat_watch_pv,
        "heat_watch_pv_share": ratio(heat_watch_pv, total_watch_pv),
        "ads_watch_pv": ads_watch_pv,
        "ads_watch_pv_share": ratio(ads_watch_pv, total_watch_pv),
    }


def fmt_num(value: int | float | None) -> str:
    if value is None:
        return "未提供"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    return f"{int(value):,}"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "未提供"
    return f"{value * 100:.1f}%"


def fmt_dt(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(int(value), CN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(value)


def max_row(rows: list[Row], attr: str) -> Row | None:
    valid = [r for r in rows if getattr(r, attr) not in (None, "")]
    if not valid:
        return None
    return max(valid, key=lambda r: getattr(r, attr) or 0)


def safe_mean(values: list[float | int]) -> float:
    return mean(values) if values else 0.0


def split_phases(rows: list[Row]) -> list[tuple[str, list[Row]]]:
    n = len(rows)
    if n >= 80:
        spans = [
            ("开场冷启动", 0, 12),
            ("平台放量", 12, 27),
            ("高在线承接", 27, 47),
            ("回落维持", 47, 72),
            ("尾段稳定", 72, n),
        ]
    else:
        cuts = [0, round(n * 0.15), round(n * 0.35), round(n * 0.60), round(n * 0.85), n]
        labels = ["开场冷启动", "平台放量", "高在线承接", "回落维持", "尾段稳定"]
        spans = [(label, cuts[i], cuts[i + 1]) for i, label in enumerate(labels)]
    return [(label, rows[start:end]) for label, start, end in spans if rows[start:end]]


def phase_stats(rows: list[Row]) -> list[dict[str, Any]]:
    stats = []
    for label, part in split_phases(rows):
        rates = [r.entry_rate for r in part if r.entry_rate is not None]
        stats.append(
            {
                "label": label,
                "range": f"{part[0].time}-{part[-1].time}",
                "minutes": len(part),
                "avg_exposure": safe_mean([r.exposure for r in part]),
                "avg_entry": safe_mean([r.entry for r in part]),
                "avg_online": safe_mean([r.online for r in part]),
                "transaction_amount": sum(r.transaction_amount or 0 for r in part),
                "order_count": sum(r.order_count for r in part),
                "buyer_count": sum(r.buyer_count for r in part),
                "entry_rate": safe_mean(rates),
                "peak_exposure": max_row(part, "exposure"),
                "peak_entry": max_row(part, "entry"),
                "peak_online": max_row(part, "online"),
            }
        )
    return stats


def best_windows(rows: list[Row], size: int = 5) -> dict[str, dict[str, Any]]:
    if len(rows) < size:
        return {}
    windows = []
    for i in range(len(rows) - size + 1):
        part = rows[i : i + size]
        exposure_sum = sum(r.exposure for r in part)
        windows.append(
            {
                "range": f"{part[0].time}-{part[-1].time}",
                "avg_exposure": safe_mean([r.exposure for r in part]),
                "avg_entry": safe_mean([r.entry for r in part]),
                "avg_online": safe_mean([r.online for r in part]),
                "entry_rate": (sum(r.entry for r in part) / exposure_sum) if exposure_sum else 0,
            }
        )
    return {
        "exposure": max(windows, key=lambda w: w["avg_exposure"]),
        "entry": max(windows, key=lambda w: w["avg_entry"]),
        "online": max(windows, key=lambda w: w["avg_online"]),
        "entry_rate": max(windows, key=lambda w: w["entry_rate"]),
    }


def row_index(rows: list[Row], target: Row | None) -> int:
    if target is None:
        return -1
    for i, row in enumerate(rows):
        if row.time == target.time and row.ts == target.ts:
            return i
    return -1


def build_findings(rows: list[Row], phases: list[dict[str, Any]]) -> list[str]:
    exposure_peak = max_row(rows, "exposure")
    online_peak = max_row(rows, "online")
    transaction_rows = [r for r in rows if (r.transaction_amount or 0) > 0 or r.order_count > 0]
    transaction_peak = max_row(transaction_rows, "transaction_amount") if transaction_rows else None
    findings: list[str] = []
    exposure_idx = row_index(rows, exposure_peak)
    online_idx = row_index(rows, online_peak)
    if exposure_idx >= 0 and online_idx >= 0 and online_idx - exposure_idx >= 5:
        findings.append("平台先给量，在线峰值滞后，说明内容承接是在中段变好。")
    elif exposure_idx >= 0 and online_idx >= 0 and exposure_idx - online_idx >= 5:
        findings.append("在线峰值早于曝光峰值，说明前段留存更强，后续给量没有同等承接。")
    else:
        findings.append("曝光峰值和在线峰值接近，平台给量与内容承接基本同步。")

    if phases:
        first_two = phases[:2]
        later = phases[2:]
        early_rate = safe_mean([p["entry_rate"] for p in first_two if p["entry_rate"]])
        later_rate = safe_mean([p["entry_rate"] for p in later if p["entry_rate"]])
        if later_rate and early_rate and later_rate > early_rate * 1.2:
            findings.append("后半段进房率明显高于前半段，前段推荐流量存在浪费。")
        elif early_rate and later_rate and early_rate > later_rate * 1.2:
            findings.append("前半段进房效率更强，后半段需要更换钩子或货品动作。")
        else:
            findings.append("前后段进房率差异不大，核心问题更可能在平台给量规模。")

    tail = phases[-1] if phases else None
    peak_online = online_peak.online if online_peak else 0
    if tail and peak_online and tail["avg_online"] >= peak_online * 0.6:
        findings.append("尾段在线仍能维持，适合转成交、关注和复盘互动，不适合重新起流量。")
    if transaction_peak:
        findings.append(f"成交发生在 {transaction_peak.time} 附近，优先回看该分钟前后 5 分钟的话术、商品展示和逼单动作。")
    return findings


def build_talent_suggestions(
    rows: list[Row],
    phases: list[dict[str, Any]],
    windows: dict[str, dict[str, Any]],
    transaction_rows: list[Row],
    channel: dict[str, Any],
    avg_watch_seconds: int | None,
) -> list[str]:
    suggestions: list[str] = []
    heat_share = channel.get("heat_watch_pv_share")
    exposure_window = windows.get("exposure", {}).get("range") if windows else None
    online_window = windows.get("online", {}).get("range") if windows else None

    if exposure_window:
        suggestions.append(f"把 {exposure_window} 的开场/话题提炼成固定开播钩子，前 30 秒直接说清楚“今天看什么、为什么值得停留”。")
    if online_window and online_window != exposure_window:
        suggestions.append(f"复盘 {online_window} 的留人动作，把当时的实景、冲突或互动方式提前到平台放量窗口。")
    if heat_share is not None and heat_share >= 0.1:
        suggestions.append("加热流量占比较高，进来的用户更冷，达人需要更频繁重申身份、人设和本场看点，避免只接老粉语境。")
    if avg_watch_seconds is not None and avg_watch_seconds < 120:
        suggestions.append("平均观看低于 2 分钟，每 60-90 秒要重置一次看点：问题、反差、下一处实景或下一段答案。")
    if not transaction_rows:
        suggestions.append("如果本场要转成交，高在线窗口必须插入软转化动作：关注、预约、商品使用场景或小黄车提醒。")
    else:
        transaction_peak = max_row(transaction_rows, "transaction_amount")
        if transaction_peak:
            suggestions.append(f"保留 {transaction_peak.time} 附近的成交话术，下一场提前到首个高在线窗口测试。")
    return suggestions[:4]


def build_operator_suggestions(
    rows: list[Row],
    phases: list[dict[str, Any]],
    windows: dict[str, dict[str, Any]],
    transaction_rows: list[Row],
    channel: dict[str, Any],
) -> list[str]:
    suggestions: list[str] = []
    heat_share = channel.get("heat_watch_pv_share")
    exposure_window = windows.get("exposure", {}).get("range") if windows else None
    entry_window = windows.get("entry", {}).get("range") if windows else None
    online_window = windows.get("online", {}).get("range") if windows else None

    if exposure_window:
        suggestions.append(f"把 {exposure_window} 标记为平台放量样本，回看封面、标题、开场 30 秒和评论区提问。")
    if entry_window and online_window:
        suggestions.append(f"对比 {entry_window} 进房峰值和 {online_window} 在线峰值，拆出“吸点击动作”和“留人动作”分别复用。")
    if heat_share is not None:
        suggestions.append(f"本场加热看播占比 {fmt_pct(heat_share)}，运营复盘时必须把自然流量和加热流量分开判断。")
    else:
        suggestions.append("补查渠道流量分析；如果加热字段缺失，不要把整场流量表现直接归因给自然推荐。")
    if transaction_rows:
        transaction_peak = max_row(transaction_rows, "transaction_amount")
        if transaction_peak:
            suggestions.append(f"回看 {transaction_peak.time} 前后 5 分钟，记录商品、逼单话术、评论问题和成交触发点。")
    else:
        suggestions.append("如果目标是带货，运营要补商品榜/订单数据，并在高在线窗口设计明确的转化节点。")
    return suggestions[:4]


def build_markdown(csv_path: Path, raw_path: Path | None, rows: list[Row], raw: dict[str, Any]) -> str:
    if len([r for r in rows if r.exposure or r.entry or r.online]) < 10:
        return (
            "结论：\n数据不足，不能做整场趋势判断。\n\n"
            "数据口径：\n"
            f"- CSV：{csv_path}\n"
            f"- raw：{raw_path or '未提供'}\n"
            f"- 有效分钟点：{len(rows)}\n"
        )

    meta = raw.get("meta") or {}
    overview = raw.get("overview") or {}
    phases = phase_stats(rows)
    windows = best_windows(rows)
    exposure_peak = max_row(rows, "exposure")
    entry_peak = max_row(rows, "entry")
    online_peak = max_row(rows, "online")
    transaction_rows = [r for r in rows if (r.transaction_amount or 0) > 0 or r.order_count > 0]
    transaction_peak = max_row(transaction_rows, "transaction_amount") if transaction_rows else None
    total_amount = sum(r.transaction_amount or 0 for r in rows)
    total_orders = sum(r.order_count for r in rows)
    total_buyers = sum(r.buyer_count for r in rows)
    total_entry = sum(r.entry for r in rows)
    total_exposure = sum(r.exposure for r in rows)
    amount_per_entry = total_amount / total_entry if total_entry else None
    amount_per_1000_exposure = total_amount / total_exposure * 1000 if total_exposure else None
    findings = build_findings(rows, phases)

    impression_uv = metric_int(overview, "impressionUv")
    watch_uv = metric_int(overview, "cumulativeWatchUv")
    watch_rate = (watch_uv / impression_uv) if impression_uv else None
    avg_online = metric_int(overview, "averageOnlineWatchUvPerMinute")
    peak_online = metric_int(overview, "peakOnlineWatchUv")
    avg_watch_seconds = metric_int(overview, "averageWatchSecondsPerAudience")
    comments = metric_int(overview, "cumulativeCommentPv")
    follows = metric_int(overview, "cumulativeNewFollowUv")
    channel = channel_traffic(raw)
    talent_suggestions = build_talent_suggestions(rows, phases, windows, transaction_rows, channel, avg_watch_seconds)
    operator_suggestions = build_operator_suggestions(rows, phases, windows, transaction_rows, channel)

    live_name = meta.get("anchorNickname") or "未提供"
    live_title = meta.get("liveDescription") or "未提供"
    start = fmt_dt(meta.get("createTime"))
    end = fmt_dt(meta.get("endTime"))

    lines = [
        "结论：",
        f"{findings[0]}{findings[1] if len(findings) > 1 else ''}",
        "",
        "数据口径：",
        f"- CSV：{csv_path}",
        f"- raw：{raw_path or '未提供'}",
        f"- 场次：{live_name}《{live_title}》",
        f"- 时间：{start or rows[0].time} 至 {end or rows[-1].time}",
        f"- 分钟点：{len(rows)}",
        "",
        "整场基础盘：",
        f"- 曝光 UV：{fmt_num(impression_uv)}",
        f"- 看播 UV：{fmt_num(watch_uv)}",
        f"- 曝光到看播：{fmt_pct(watch_rate)}",
        f"- 平均在线 / 峰值在线：{fmt_num(avg_online)} / {fmt_num(peak_online)}",
        f"- 平均观看：{fmt_num(avg_watch_seconds)} 秒",
        f"- 评论 / 新增关注：{fmt_num(comments)} / {fmt_num(follows)}",
        f"- 加热看播人次 / 占比：{fmt_num(channel.get('heat_watch_pv'))} / {fmt_pct(channel.get('heat_watch_pv_share'))}",
        f"- 广告看播人次 / 占比：{fmt_num(channel.get('ads_watch_pv'))} / {fmt_pct(channel.get('ads_watch_pv_share'))}",
    ]
    if transaction_rows:
        lines.extend(
            [
                f"- 成交金额 / 订单 / 买家：¥{total_amount:,.2f} / {total_orders} / {total_buyers}",
                f"- 单进房成交额：¥{amount_per_entry:.2f}" if amount_per_entry is not None else "- 单进房成交额：未提供",
                f"- 千次曝光成交额：¥{amount_per_1000_exposure:.2f}" if amount_per_1000_exposure is not None else "- 千次曝光成交额：未提供",
            ]
        )
    lines.extend(
        [
            "",
            "关键时间点：",
            f"- 曝光峰值：{exposure_peak.time}，曝光 {exposure_peak.exposure}，进房 {exposure_peak.entry}，在线 {exposure_peak.online}",
            f"- 进房峰值：{entry_peak.time}，曝光 {entry_peak.exposure}，进房 {entry_peak.entry}，在线 {entry_peak.online}",
            f"- 在线峰值：{online_peak.time}，曝光 {online_peak.exposure}，进房 {online_peak.entry}，在线 {online_peak.online}",
        ]
    )
    if transaction_peak:
        lines.append(
            f"- 成交峰值：{transaction_peak.time}，成交 ¥{transaction_peak.transaction_amount or 0:,.2f}，订单 {transaction_peak.order_count}，买家 {transaction_peak.buyer_count}"
        )
    lines.extend(["", "趋势拆解："])
    for i, p in enumerate(phases, start=1):
        line = (
            f"{i}. {p['label']}（{p['range']}）：平均曝光 {p['avg_exposure']:.1f}，"
            f"平均进房 {p['avg_entry']:.1f}，平均在线 {p['avg_online']:.1f}，进房率 {fmt_pct(p['entry_rate'])}"
        )
        if transaction_rows:
            line += f"，成交 ¥{p['transaction_amount']:,.2f}，订单 {p['order_count']}"
        lines.append(line)

    if windows:
        lines.extend(
            [
                "",
                "最佳 5 分钟窗口：",
                f"- 曝光：{windows['exposure']['range']}，平均曝光 {windows['exposure']['avg_exposure']:.1f}",
                f"- 进房：{windows['entry']['range']}，平均进房 {windows['entry']['avg_entry']:.1f}",
                f"- 在线：{windows['online']['range']}，平均在线 {windows['online']['avg_online']:.1f}",
                f"- 进房率：{windows['entry_rate']['range']}，进房率 {fmt_pct(windows['entry_rate']['entry_rate'])}",
            ]
        )

    lines.extend(
        [
            "",
            "判断：",
            f"1. {findings[0]}",
            f"2. {findings[1] if len(findings) > 1 else '进房效率需要结合封面、标题、开场话术复盘。'}",
            f"3. {findings[2] if len(findings) > 2 else '在线留存需要回看峰值时间段确认内容动作。'}",
            "",
            "下一步：",
            f"1. 回看 {(transaction_peak or online_peak).time} 前后 5 分钟，记录当时话题、货品动作、评论互动和成交话术。",
            f"2. 回看 {exposure_peak.time} 前后 5 分钟，检查平台给量时的封面/标题/开场钩子是否承接住。",
            "",
            "给达人建议：",
            *[f"{i}. {text}" for i, text in enumerate(talent_suggestions, start=1)],
            "",
            "给运营建议：",
            *[f"{i}. {text}" for i, text in enumerate(operator_suggestions, start=1)],
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON summary instead of Markdown.")
    args = parser.parse_args()

    rows = read_rows(args.csv)
    raw = read_raw(args.raw)
    phases = phase_stats(rows)
    windows = best_windows(rows)
    transaction_rows = [r for r in rows if (r.transaction_amount or 0) > 0 or r.order_count > 0]
    overview = raw.get("overview") or {}
    channel = channel_traffic(raw)
    avg_watch_seconds = metric_int(overview, "averageWatchSecondsPerAudience")
    result = {
        "csv": str(args.csv),
        "raw": str(args.raw) if args.raw else "",
        "rows": len(rows),
        "peaks": {
            "exposure": max_row(rows, "exposure").__dict__ if rows else None,
            "entry": max_row(rows, "entry").__dict__ if rows else None,
            "online": max_row(rows, "online").__dict__ if rows else None,
            "transaction_amount": max_row([r for r in rows if (r.transaction_amount or 0) > 0], "transaction_amount").__dict__
            if any((r.transaction_amount or 0) > 0 for r in rows)
            else None,
        },
        "totals": {
            "transaction_amount": round(sum(r.transaction_amount or 0 for r in rows), 2),
            "order_count": sum(r.order_count for r in rows),
            "buyer_count": sum(r.buyer_count for r in rows),
        },
        "phases": [
            {
                **{k: v for k, v in phase.items() if not k.startswith("peak_")},
                "peak_exposure": phase["peak_exposure"].__dict__ if phase.get("peak_exposure") else None,
                "peak_entry": phase["peak_entry"].__dict__ if phase.get("peak_entry") else None,
                "peak_online": phase["peak_online"].__dict__ if phase.get("peak_online") else None,
            }
            for phase in phases
        ],
        "best_windows": best_windows(rows),
        "findings": build_findings(rows, phases),
        "channel_traffic": channel,
        "talent_suggestions": build_talent_suggestions(rows, phases, windows, transaction_rows, channel, avg_watch_seconds),
        "operator_suggestions": build_operator_suggestions(rows, phases, windows, transaction_rows, channel),
        "meta": raw.get("meta") or {},
        "overview": raw.get("overview") or {},
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(build_markdown(args.csv, args.raw, rows, raw))


if __name__ == "__main__":
    main()
