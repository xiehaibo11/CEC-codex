"""Chinese display helpers for event-contract user-facing text."""

from __future__ import annotations

from typing import Iterable


REVIEWER_NAME_ZH = {
    "Main Logic": "主体逻辑",
    "Trend Micro AI": "微趋势评审",
    "Trend Structure AI": "趋势结构评审",
    "Momentum AI": "动量评审",
    "Volume AI": "成交量评审",
    "Volatility AI": "波动率评审",
    "Kline Pattern AI": "K线形态评审",
    "Wick Rejection AI": "影线拒绝评审",
    "Breakout AI": "突破评审",
    "Fake Breakout AI": "假突破评审",
    "Pullback AI": "回调评审",
    "Range AI": "震荡区间评审",
    "Trap Detection AI": "陷阱检测评审",
    "Bull Trap AI": "多头陷阱评审",
    "Bear Trap AI": "空头陷阱评审",
    "Liquidity Sweep AI": "流动性扫单评审",
    "Stop Hunt AI": "止损猎杀评审",
    "Orderbook AI": "订单簿评审",
    "Spread AI": "价差评审",
    "CVD AI": "CVD评审",
    "Taker Ratio AI": "主动买卖比评审",
    "Open Interest AI": "持仓量评审",
    "Funding Rate AI": "资金费率评审",
    "Liquidation AI": "爆仓评审",
    "Support Resistance AI": "支撑阻力评审",
    "VWAP AI": "VWAP评审",
    "Multi Timeframe AI": "多周期评审",
    "Market Regime AI": "市场状态评审",
    "Noise Filter AI": "噪音过滤评审",
    "Entry Timing AI": "入场时机评审",
    "Final Risk AI": "最终风险评审",
}

DIRECTION_ZH = {
    "long": "做多",
    "short": "做空",
    "hold": "观望",
}

SOURCE_LABEL_ZH = {
    "llm_ai": "大模型评审",
    "system_panel": "规则面板",
    "main_logic": "主体逻辑",
    "rule_prefilter": "规则预筛",
}

CVD_SOURCE_ZH = {
    "OHLCV proxy": "OHLCV 代理",
}


def localize_reviewer_name(name: str) -> str:
    if name in REVIEWER_NAME_ZH:
        return REVIEWER_NAME_ZH[name]
    if name.endswith(" Rule Agent"):
        return name.replace(" Rule Agent", "规则评审")
    if name.endswith(" AI"):
        return name.replace(" AI", "评审")
    return name


def localize_reviewer_names(names: Iterable[str]) -> str:
    return "、".join(localize_reviewer_name(name) for name in names)


def join_chinese_reasons(reasons: Iterable[str]) -> str:
    return "；".join(reason for reason in reasons if reason)


def localize_direction(direction: str) -> str:
    return DIRECTION_ZH.get(direction, direction)


def localize_source_label(source: str) -> str:
    return SOURCE_LABEL_ZH.get(source, source)


def localize_cvd_source(source: str) -> str:
    return CVD_SOURCE_ZH.get(source, source)
