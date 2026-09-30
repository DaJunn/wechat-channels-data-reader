#!/usr/bin/env python3
import argparse
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP


ALIASES = {
    "gmv": ["gmv", "GMV", "累计成交金额", "成交金额"],
    "orders": ["orders", "成交订单数", "成交单数"],
    "estimated_commission": ["estimated_commission", "预估佣金", "佣金"],
    "refund_rate": ["refund_rate", "退款率", "退货率"],
    "mcn_share": ["mcn_share", "MCN分成", "小浪花分成"],
    "company_cost": ["company_cost", "公司成本", "投流成本", "成本"],
}


def pick(data, key, default=None):
    for name in ALIASES.get(key, [key]):
        if name in data and data[name] not in (None, ""):
            return data[name]
    return default


def money(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    s = str(value).strip().replace(",", "")
    multiplier = Decimal("1")
    if "万" in s:
        multiplier = Decimal("10000")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    return Decimal(s) * multiplier


def number(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    s = str(value).strip().replace(",", "")
    multiplier = Decimal("1")
    if "万" in s:
        multiplier = Decimal("10000")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    return Decimal(s) * multiplier


def percent(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, (int, float, Decimal)):
        d = Decimal(str(value))
    else:
        s = str(value).strip()
        has_pct = "%" in s
        s = re.sub(r"[^\d.\-]", "", s)
        if not s:
            return default
        d = Decimal(s)
        if has_pct:
            d = d / Decimal("100")
    if d > 1:
        d = d / Decimal("100")
    return d


def q2(value):
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pct2(value):
    if value is None:
        return None
    return (value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main():
    parser = argparse.ArgumentParser(description="Calculate WeChat Channels live commerce metrics.")
    parser.add_argument("input", nargs="?", help="JSON file path. Reads stdin when omitted.")
    args = parser.parse_args()

    raw = open(args.input, "r", encoding="utf-8").read() if args.input else sys.stdin.read()
    data = json.loads(raw)

    gmv = money(pick(data, "gmv"))
    orders = number(pick(data, "orders"))
    commission = money(pick(data, "estimated_commission"))
    refund_rate = percent(pick(data, "refund_rate"), Decimal("0"))
    mcn_share = percent(pick(data, "mcn_share"), Decimal("0.40"))
    company_cost = money(pick(data, "company_cost"))

    avg_order_value = gmv / orders if gmv is not None and orders and orders != 0 else None
    commission_rate = commission / gmv if commission is not None and gmv and gmv != 0 else None
    company_revenue = commission * mcn_share * (Decimal("1") - refund_rate) if commission is not None else None
    gross_profit = company_revenue - company_cost if company_revenue is not None and company_cost is not None else None

    result = {
        "input": {
            "talent": data.get("talent") or data.get("达人"),
            "live_title": data.get("live_title") or data.get("直播标题"),
            "started_at": data.get("started_at") or data.get("开播时间"),
            "source": data.get("source") or data.get("来源"),
        },
        "metrics": {
            "gmv": str(q2(gmv)) if gmv is not None else None,
            "orders": int(orders) if orders is not None else None,
            "avg_order_value": str(q2(avg_order_value)) if avg_order_value is not None else None,
            "estimated_commission": str(q2(commission)) if commission is not None else None,
            "commission_rate_percent": str(pct2(commission_rate)) if commission_rate is not None else None,
            "refund_rate_percent": str(pct2(refund_rate)) if refund_rate is not None else None,
            "mcn_share_percent": str(pct2(mcn_share)) if mcn_share is not None else None,
            "company_revenue_after_refund": str(q2(company_revenue)) if company_revenue is not None else None,
            "company_cost": str(q2(company_cost)) if company_cost is not None else None,
            "company_gross_profit": str(q2(gross_profit)) if gross_profit is not None else None,
        },
        "formula": "company_revenue_after_refund = estimated_commission * mcn_share * (1 - refund_rate)",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
