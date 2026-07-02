"""Independent AI-trader team research report for event-contract backtests.

This module is deliberately separate from consensus voting.  Each configured
AI rule reviewer is treated as its own virtual trader: if it says long/short,
the backtest settles that trader's event contract independently; if it says
hold, only that trader skips the bar.  The report is research-only and never
changes the main strategy's trades or PnL.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

from services.event_contract.constants import EVENT_AI_NAMES


TRADER_METADATA: Dict[str, Dict[str, Any]] = {
    "Trend Micro AI": {
        "name": "趋势微结构AI交易员",
        "strategy_type": "微趋势跟随",
        "factor_focus": ["短周期趋势", "EMA斜率", "1m/3m动量"],
    },
    "Trend Structure AI": {
        "name": "趋势结构AI交易员",
        "strategy_type": "结构趋势交易",
        "factor_focus": ["高低点结构", "支撑阻力", "趋势延续"],
    },
    "Momentum AI": {
        "name": "动量AI交易员",
        "strategy_type": "动量延续",
        "factor_focus": ["3m收益", "5m收益", "RSI"],
    },
    "Volume AI": {
        "name": "成交量AI交易员",
        "strategy_type": "量能确认",
        "factor_focus": ["成交量倍率", "量价一致性", "突破确认"],
    },
    "Volatility AI": {
        "name": "波动率AI交易员",
        "strategy_type": "波动窗口过滤",
        "factor_focus": ["ATR%", "波动扩张", "低波动过滤"],
    },
    "Kline Pattern AI": {
        "name": "K线形态AI交易员",
        "strategy_type": "K线形态",
        "factor_focus": ["实体比例", "收盘位置", "单K方向"],
    },
    "Wick Rejection AI": {
        "name": "影线拒绝AI交易员",
        "strategy_type": "影线反转",
        "factor_focus": ["上影线", "下影线", "拒绝位"],
    },
    "Breakout AI": {
        "name": "突破AI交易员",
        "strategy_type": "突破延续",
        "factor_focus": ["区间突破", "高低点突破", "趋势确认"],
    },
    "Fake Breakout AI": {
        "name": "假突破AI交易员",
        "strategy_type": "假突破过滤",
        "factor_focus": ["假突破风险", "收盘确认", "突破失败"],
    },
    "Pullback AI": {
        "name": "回调AI交易员",
        "strategy_type": "趋势回调",
        "factor_focus": ["VWAP回踩", "EMA回踩", "趋势延续"],
    },
    "Range AI": {
        "name": "震荡区间AI交易员",
        "strategy_type": "区间风险过滤",
        "factor_focus": ["区间位置", "震荡风险", "中部禁区"],
    },
    "Trap Detection AI": {
        "name": "陷阱检测AI交易员",
        "strategy_type": "陷阱规避",
        "factor_focus": ["多空陷阱", "诱多诱空", "风险门槛"],
    },
    "Bull Trap AI": {
        "name": "多头陷阱AI交易员",
        "strategy_type": "诱多过滤",
        "factor_focus": ["多头陷阱", "上方扫流动性", "失败突破"],
    },
    "Bear Trap AI": {
        "name": "空头陷阱AI交易员",
        "strategy_type": "诱空过滤",
        "factor_focus": ["空头陷阱", "下方扫流动性", "失败跌破"],
    },
    "Liquidity Sweep AI": {
        "name": "流动性扫单AI交易员",
        "strategy_type": "扫流动性反应",
        "factor_focus": ["流动性扫单", "影线", "关键价位"],
    },
    "Stop Hunt AI": {
        "name": "止损猎杀AI交易员",
        "strategy_type": "止损猎杀识别",
        "factor_focus": ["扫损", "假跌破", "假突破"],
    },
    "Orderbook AI": {
        "name": "盘口AI交易员",
        "strategy_type": "盘口失衡",
        "factor_focus": ["订单簿失衡", "买卖墙", "盘口深度"],
    },
    "Spread AI": {
        "name": "点差AI交易员",
        "strategy_type": "执行质量过滤",
        "factor_focus": ["点差", "盘口流动性", "执行成本"],
    },
    "CVD AI": {
        "name": "CVD AI交易员",
        "strategy_type": "主动买卖流",
        "factor_focus": ["CVD", "主动买入", "主动卖出"],
    },
    "Taker Ratio AI": {
        "name": "主动成交比AI交易员",
        "strategy_type": "主动成交方向",
        "factor_focus": ["Taker买卖比", "成交流", "订单流代理"],
    },
    "Open Interest AI": {
        "name": "持仓量AI交易员",
        "strategy_type": "持仓变化确认",
        "factor_focus": ["OI变化", "增仓方向", "减仓风险"],
    },
    "Funding Rate AI": {
        "name": "资金费率AI交易员",
        "strategy_type": "资金费率过滤",
        "factor_focus": ["资金费率", "拥挤方向", "反身性"],
    },
    "Liquidation AI": {
        "name": "爆仓AI交易员",
        "strategy_type": "爆仓流反应",
        "factor_focus": ["多空爆仓", "清算失衡", "挤压风险"],
    },
    "Support Resistance AI": {
        "name": "支撑阻力AI交易员",
        "strategy_type": "关键位交易",
        "factor_focus": ["支撑", "阻力", "区间位置"],
    },
    "VWAP AI": {
        "name": "VWAP AI交易员",
        "strategy_type": "VWAP偏离",
        "factor_focus": ["VWAP", "均价偏离", "回归/延续"],
    },
    "Multi Timeframe AI": {
        "name": "多周期AI交易员",
        "strategy_type": "多周期一致性",
        "factor_focus": ["1m方向", "3m方向", "5m方向", "15m方向"],
    },
    "Market Regime AI": {
        "name": "市场状态AI交易员",
        "strategy_type": "Regime路由",
        "factor_focus": ["趋势", "震荡", "假突破", "回调"],
    },
    "Noise Filter AI": {
        "name": "噪音过滤AI交易员",
        "strategy_type": "噪音过滤",
        "factor_focus": ["实体比例", "ATR", "低质量K线"],
    },
    "Entry Timing AI": {
        "name": "入场时机AI交易员",
        "strategy_type": "入场质量",
        "factor_focus": ["影线风险", "盘口反向", "即时入场"],
    },
    "Final Risk AI": {
        "name": "最终风控AI交易员",
        "strategy_type": "综合风控",
        "factor_focus": ["陷阱风险", "假突破风险", "区间风险"],
    },
}


def build_ai_trader_team_state(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Create isolated state for all independent AI traders."""

    initial_balance = float(cfg.get("initial_balance") or 0)
    return {
        "initial_balance": initial_balance,
        "traders": {
            ai_name: {
                "ai_name": ai_name,
                "equity": initial_balance,
                "peak_equity": initial_balance,
                "max_drawdown": 0.0,
                "trades": [],
                "hold_count": 0,
                "missing_decision_count": 0,
                "evaluated_count": 0,
            }
            for ai_name in EVENT_AI_NAMES
        },
    }


def record_ai_trader_team_decisions(
    *,
    state: Dict[str, Any],
    cfg: Dict[str, Any],
    decisions: Sequence[Dict[str, Any]],
    signal_time: str,
    entry_time: str,
    expiry_time: str,
    entry_price: float,
    expiry_price: float,
    market_state: str,
) -> None:
    """Settle one decision bar for every independent AI trader."""

    decision_map = {str(item.get("ai_name")): item for item in decisions}
    for ai_name in EVENT_AI_NAMES:
        trader = state["traders"][ai_name]
        trader["evaluated_count"] += 1
        decision = decision_map.get(ai_name)
        if not decision:
            trader["missing_decision_count"] += 1
            continue
        direction = str(decision.get("direction") or "hold")
        if direction not in {"long", "short"}:
            trader["hold_count"] += 1
            continue

        adjusted_entry = _apply_slippage(float(entry_price), direction, float(cfg.get("slippage_bps") or 0))
        result = _settle_event_contract(direction, adjusted_entry, float(expiry_price), str(cfg.get("draw_result") or "loss"))
        pnl = _event_contract_pnl(result, cfg)
        equity_before = float(trader["equity"])
        equity_after = equity_before + pnl
        trader["equity"] = equity_after
        trader["peak_equity"] = max(float(trader["peak_equity"]), equity_after)
        peak = float(trader["peak_equity"])
        if peak > 0:
            trader["max_drawdown"] = max(float(trader["max_drawdown"]), (peak - equity_after) / peak * 100)

        trade_index = len(trader["trades"]) + 1
        trader["trades"].append(
            {
                "trade_index": trade_index,
                "signal_time": signal_time,
                "entry_time": entry_time,
                "expiry_time": expiry_time,
                "direction": direction,
                "entry_price": round(adjusted_entry, 6),
                "expiry_price": round(float(expiry_price), 6),
                "result": result,
                "profit_loss": round(pnl, 6),
                "equity_before": round(equity_before, 4),
                "equity_after": round(equity_after, 4),
                "confidence": _round_float(decision.get("confidence")),
                "reason": str(decision.get("reason") or ""),
                "risk_flags": list(decision.get("risk_flags") or []),
                "market_state": market_state,
            }
        )


def finalize_ai_trader_team_report(state: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Build a ranked research report for the independent trader team."""

    traders = [_build_trader_report(ai_name, state["traders"][ai_name], cfg) for ai_name in EVENT_AI_NAMES]
    ranked = sorted(
        traders,
        key=lambda item: (
            item["recommendation_rank"],
            item["oos_win_rate"],
            item["win_rate"],
            item["pnl"],
            item["trade_count"],
        ),
        reverse=True,
    )
    paper_candidates = [item for item in ranked if item["recommendation"] == "可进入纸盘观察"]
    rejected = [item for item in ranked if item["recommendation"].startswith("拒绝") or "过拟合" in item["recommendation"]]
    return {
        "mode": "independent_traders",
        "description": "30个AI交易员独立开仓、独立结算、独立排名；不是共同投票。",
        "total_traders": len(EVENT_AI_NAMES),
        "total_team_trades": sum(item["trade_count"] for item in traders),
        "top_traders": ranked[:5],
        "paper_candidates": paper_candidates[:10],
        "rejected_traders": rejected[:10],
        "traders": traders,
    }


def _build_trader_report(ai_name: str, trader: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    metadata = TRADER_METADATA.get(ai_name, {})
    trades = list(trader.get("trades") or [])
    metrics = _trade_metrics(trades)
    split = _split_index(metrics["trade_count"])
    train = trades[:split]
    oos = trades[split:]
    train_metrics = _trade_metrics(train)
    oos_metrics = _trade_metrics(oos)
    break_even = _break_even_win_rate(cfg)
    target = float(cfg.get("target_win_rate") if cfg.get("target_win_rate") is not None else 75)
    gap = round(train_metrics["win_rate"] - oos_metrics["win_rate"], 2)
    risk = _overfit_risk(
        gap=gap,
        train_count=train_metrics["trade_count"],
        oos_count=oos_metrics["trade_count"],
        oos_win_rate=oos_metrics["win_rate"],
        break_even=break_even,
    )
    recommendation, rank = _recommendation(metrics, oos_metrics, risk, cfg, target, break_even)
    return {
        "trader_id": _safe_id(ai_name),
        "ai_name": ai_name,
        "name": metadata.get("name") or f"{ai_name}交易员",
        "strategy_type": metadata.get("strategy_type") or "独立规则交易",
        "factor_focus": list(metadata.get("factor_focus") or []),
        "evaluated_count": int(trader.get("evaluated_count") or 0),
        "hold_count": int(trader.get("hold_count") or 0),
        "missing_decision_count": int(trader.get("missing_decision_count") or 0),
        "trade_count": metrics["trade_count"],
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "draws": metrics["draws"],
        "win_rate": metrics["win_rate"],
        "pnl": metrics["pnl"],
        "max_drawdown": round(float(trader.get("max_drawdown") or 0), 4),
        "train_trade_count": train_metrics["trade_count"],
        "train_win_rate": train_metrics["win_rate"],
        "train_pnl": train_metrics["pnl"],
        "oos_trade_count": oos_metrics["trade_count"],
        "oos_win_rate": oos_metrics["win_rate"],
        "oos_pnl": oos_metrics["pnl"],
        "win_rate_gap": gap,
        "overfit_risk": risk,
        "break_even_win_rate": round(break_even, 2),
        "target_win_rate": round(target, 2),
        "recommendation": recommendation,
        "recommendation_rank": rank,
    }


def _trade_metrics(trades: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    trade_count = len(trades)
    wins = sum(1 for trade in trades if trade.get("result") == "win")
    losses = sum(1 for trade in trades if trade.get("result") == "loss")
    draws = sum(1 for trade in trades if trade.get("result") == "draw")
    pnl = round(sum(float(trade.get("profit_loss") or 0) for trade in trades), 4)
    return {
        "trade_count": trade_count,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(wins / trade_count * 100, 2) if trade_count else 0.0,
        "pnl": pnl,
    }


def _recommendation(
    metrics: Dict[str, Any],
    oos_metrics: Dict[str, Any],
    risk: str,
    cfg: Dict[str, Any],
    target: float,
    break_even: float,
) -> tuple[str, int]:
    min_trades = int(cfg.get("target_min_trades") or 10)
    if metrics["trade_count"] < min_trades:
        return "样本不足", 0
    if risk in {"critical", "high"}:
        return "高过拟合风险，不建议交易", 1
    if oos_metrics["win_rate"] >= target and metrics["pnl"] > 0:
        return "可进入纸盘观察", 4
    if oos_metrics["win_rate"] >= break_even and metrics["pnl"] > 0:
        return "研究候选，继续观察", 3
    return "拒绝，未超过可交易门槛", 2


def _settle_event_contract(direction: str, entry: float, expiry: float, draw_result: str) -> str:
    if expiry == entry:
        return "draw" if draw_result == "draw" else "loss"
    if direction == "long":
        return "win" if expiry > entry else "loss"
    if direction == "short":
        return "win" if expiry < entry else "loss"
    return "loss"


def _event_contract_pnl(result: str, cfg: Dict[str, Any]) -> float:
    stake = float(cfg.get("stake_amount") or 0)
    fee = stake * float(cfg.get("fee_rate") or 0)
    if result == "win":
        return stake * float(cfg.get("win_payout_ratio") or 0) - fee
    if result == "draw":
        return -fee
    return -stake - fee


def _apply_slippage(price: float, direction: str, bps: float) -> float:
    if not bps:
        return price
    multiplier = bps / 10000
    return price * (1 + multiplier) if direction == "long" else price * (1 - multiplier)


def _split_index(total: int) -> int:
    if total <= 1:
        return total
    return min(total - 1, max(1, int(total * 0.70)))


def _overfit_risk(gap: float, train_count: int, oos_count: int, oos_win_rate: float, break_even: float) -> str:
    if train_count == 0 and oos_count == 0:
        return "none"
    if oos_count < 10:
        return "high"
    if gap >= 25 or (gap >= 15 and oos_win_rate < break_even):
        return "critical"
    if gap >= 15:
        return "high"
    if gap >= 8:
        return "medium"
    return "low"


def _break_even_win_rate(cfg: Dict[str, Any]) -> float:
    stake = float(cfg.get("stake_amount") or 100)
    payout = float(cfg.get("win_payout_ratio") or 0.8)
    fee = stake * float(cfg.get("fee_rate") or 0)
    if payout <= -1:
        return 100.0
    return round((stake + fee) / (stake * (payout + 1)) * 100, 2)


def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _round_float(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0
