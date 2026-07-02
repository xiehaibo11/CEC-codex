# Backtest Tool（事件合约）可信度改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 5 分钟事件合约回测消除数据泄漏、贴近真实平台规则（HIBT/币安事件合约）、输出统计学可信的结论，并在页面上以"可信度卡片"呈现。

**Architecture:** 后端改造集中在 `backend/services/event_contract/`（回测循环、评审员学习、统计模块、新增 platforms/constraints/stats 模块）+ 一个幂等迁移；前端在 `frontend/app/components/backtest/` 加平台预设选择器与可信度卡片。API 响应字段只增不改。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / pytest（`cd backend && uv run pytest`）；React 18 + TS + i18next（验证 `pnpm build:frontend`）。

**Spec:** `docs/superpowers/specs/2026-07-02-backtest-tool-credibility-design.md`

## Global Constraints

- 后端命令均在 `backend/` 下执行：`uv run pytest path::test -v`。
- 迁移必须幂等（先查列存在性），文件放 `backend/database/migrations/`，并追加到 `backend/database/migration_manager.py` 的 `MIGRATIONS` 列表。
- API 响应字段只增不改；`summary` 中新增键不得改变现有键的语义。
- 前端所有新文案必须同时加 EN（`frontend/app/locales/en.json`）和 ZH（`frontend/app/locales/zh.json`），key 放在 `backtestTool.*` 组。
- 提交信息用简短祈使句；每个 Task 一次提交；不要把工作区中与本计划无关的已有改动混入提交（用 `git add <具体文件>`）。
- 平台预设规则来源（写死为常量即可）：HIBT 赔付 0.80、无手续费、最小注 3、开单频率限制（每分钟）；币安事件合约 赔付 0.80、平局退本金、最小注 5、日亏损上限 10000。

---

### Task 1: 评审员权重时间隔离（修最严重泄漏）

**Files:**
- Modify: `backend/services/event_contract/reviewer_learning.py`
- Modify: `backend/services/event_contract/config.py`（加 `reviewer_weights_mode`）
- Modify: `backend/services/event_contract/backtest.py:26-37`（`_load_reviewer_weights`）
- Test: `backend/tests/test_reviewer_learning_time_isolation.py`

**Interfaces:**
- Produces: `fit_reviewer_stats(db, *, lookback=1500, before_ts: Optional[datetime] = None)`；`compute_reviewer_weights(db, before_ts: Optional[datetime] = None)`；cfg 新键 `reviewer_weights_mode: str`（`pre_window`/`static`/`unsafe_legacy`，默认 `pre_window`）。
- Consumes: 现有 `EVENT_AI_NAMES`、`get_base_weight(name)`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_reviewer_learning_time_isolation.py
"""Reviewer learning must only fit on trades settled BEFORE the backtest window."""
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.event_contract.reviewer_learning import fit_reviewer_stats
from services.event_contract.constants import EVENT_AI_NAMES

REVIEWER = EVENT_AI_NAMES[0]


def _make_db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE event_contract_trade_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_time TIMESTAMP,
                entry_price FLOAT,
                expiry_price FLOAT,
                ai_decision_snapshot TEXT
            )
            """
        ))
    return sessionmaker(bind=engine)()


def _insert_trade(db, entry_time: str, direction: str, won: bool):
    snapshot = json.dumps([{"ai_name": REVIEWER, "direction": direction, "confidence": 80}])
    entry, expiry = (100.0, 101.0) if (direction == "long") == won else (100.0, 99.0)
    db.execute(
        text(
            "INSERT INTO event_contract_trade_logs (entry_time, entry_price, expiry_price, ai_decision_snapshot)"
            " VALUES (:t, :e, :x, :s)"
        ),
        {"t": entry_time, "e": entry, "x": expiry, "s": snapshot},
    )
    db.commit()


def test_before_ts_excludes_in_window_trades():
    db = _make_db()
    _insert_trade(db, "2026-01-01 00:00:00", "long", won=True)   # pre-window
    _insert_trade(db, "2026-06-01 00:00:00", "long", won=True)   # in-window (must be excluded)
    cutoff = datetime(2026, 5, 1, tzinfo=timezone.utc)
    stats = fit_reviewer_stats(db, before_ts=cutoff)
    assert stats[REVIEWER].total == 1
    assert stats[REVIEWER].correct == 1


def test_no_before_ts_keeps_all_trades():
    db = _make_db()
    _insert_trade(db, "2026-01-01 00:00:00", "long", won=True)
    _insert_trade(db, "2026-06-01 00:00:00", "long", won=False)
    stats = fit_reviewer_stats(db)
    assert stats[REVIEWER].total == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_reviewer_learning_time_isolation.py -v`
Expected: FAIL（`fit_reviewer_stats() got an unexpected keyword argument 'before_ts'`）

- [ ] **Step 3: 实现**

`reviewer_learning.py` 改动：

```python
# 1) 缓存按 before_ts 分键（替换原 _CACHE 定义）
_CACHE_LOCK = threading.Lock()
_CACHE: Dict[Any, Dict[str, Any]] = {}
_LOOKBACK_TRADES = 1500


def clear_reviewer_cache() -> None:
    """Force a refit on next access."""
    with _CACHE_LOCK:
        _CACHE.clear()


# 2) fit_reviewer_stats 加 before_ts（替换函数签名与 SQL）
def fit_reviewer_stats(
    db: Session, *, lookback: int = _LOOKBACK_TRADES, before_ts: Optional[Any] = None
) -> Dict[str, ReviewerStats]:
    """Build per-reviewer posterior stats from settled trades.

    before_ts: only trades with entry_time strictly before this datetime are
    used. Pass the backtest window start to prevent in-window leakage.
    """
    stats = {name: ReviewerStats(name=name) for name in EVENT_AI_NAMES}
    try:
        if before_ts is not None:
            cutoff = before_ts.replace(tzinfo=None) if getattr(before_ts, "tzinfo", None) else before_ts
            rows = db.execute(
                text(
                    """
                    SELECT entry_price, expiry_price, ai_decision_snapshot
                    FROM event_contract_trade_logs
                    WHERE ai_decision_snapshot IS NOT NULL
                      AND entry_time < :cutoff
                    ORDER BY entry_time DESC
                    LIMIT :limit
                    """
                ),
                {"cutoff": cutoff, "limit": int(lookback)},
            ).fetchall()
        else:
            rows = db.execute(
                text(
                    """
                    SELECT entry_price, expiry_price, ai_decision_snapshot
                    FROM event_contract_trade_logs
                    WHERE ai_decision_snapshot IS NOT NULL
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": int(lookback)},
            ).fetchall()
    except Exception as exc:  # noqa: BLE001 - cold DB shouldn't crash predict()
        logger.warning("reviewer_learning: trade log scan failed (%s) - using priors only", exc)
        return stats
    # ……以下解析循环保持原样不动
```

（函数体其余部分、`from typing import ... Optional` 已有；`Any` 已导入。）

```python
# 3) compute_reviewer_weights 加 before_ts，缓存分键（替换函数头尾）
def compute_reviewer_weights(db: Session, before_ts: Optional[Any] = None) -> Dict[str, float]:
    cache_key = before_ts.isoformat() if before_ts is not None else "__latest__"
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None:
            return dict(cached["weights"])

    stats = fit_reviewer_stats(db, before_ts=before_ts)
    # ……权重计算循环保持原样……
    with _CACHE_LOCK:
        _CACHE[cache_key] = {"weights": dict(weights), "stats": stats}
    return weights
```

`get_reviewer_evolution_snapshot` 内 `compute_reviewer_weights(db)` 调用无需改（None → 现状）。

`config.py` 在 `"draw_result"` 行后加：

```python
            "reviewer_weights_mode": str(config.get("reviewer_weights_mode") or "pre_window").lower(),
```

并在 decision_policy 校验旁加：

```python
        if cfg["reviewer_weights_mode"] not in {"pre_window", "static", "unsafe_legacy"}:
            raise ValueError(f"Unsupported reviewer_weights_mode: {cfg['reviewer_weights_mode']}")
```

`backtest.py` `_load_reviewer_weights` 改为按模式分派（替换整个方法），并把两处调用 `self._load_reviewer_weights(db)` 改为 `self._load_reviewer_weights(db, cfg)`：

```python
    def _load_reviewer_weights(self, db: Session, cfg: Dict[str, Any]) -> Dict[str, float]:
        """Reviewer weights with temporal isolation.

        pre_window: fit only on trades before the window start (no leakage).
        static: expertise base weights only (fully deterministic).
        unsafe_legacy: old behavior (fits on ALL trade logs) - comparison only.
        """
        mode = str(cfg.get("reviewer_weights_mode") or "pre_window")
        try:
            if mode == "static":
                from services.event_contract.reviewer_expertise import get_base_weight
                from services.event_contract.constants import EVENT_AI_NAMES
                return {name: get_base_weight(name) for name in EVENT_AI_NAMES}
            from services.event_contract.reviewer_learning import compute_reviewer_weights
            if mode == "unsafe_legacy":
                return compute_reviewer_weights(db)
            return compute_reviewer_weights(db, before_ts=cfg["start_time"])
        except Exception as exc:  # noqa: BLE001 - weights are optional
            logger.warning("reviewer_learning weight load failed (%s) - using neutral weights", exc)
            return {}
```

注意 predict 路径 `backtest.py:98` 也要改成 `self._load_reviewer_weights(db, cfg)`（predict 的 cfg 无未来数据，pre_window 下传 `cfg["start_time"]` 亦可——predict 的 start_time 为当前时刻减一天，等价于"只用过去"）。
最后删除 `run_backtest` 末尾 `clear_reviewer_cache()` 的调用块（`backtest.py:480-486`），它是泄漏循环的一半；`get_reviewer_evolution_snapshot` 本来就总是重拟合，Dashboard 不受影响。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_reviewer_learning_time_isolation.py -v`
Expected: 2 passed

- [ ] **Step 5: 回归**

Run: `cd backend && uv run pytest tests/test_event_contract_backtest.py -x -q`
Expected: passed（该文件如引用 `_load_reviewer_weights(db)` 旧签名需同步改为 `(db, cfg)`）

- [ ] **Step 6: Commit**

```bash
git add backend/services/event_contract/reviewer_learning.py backend/services/event_contract/config.py backend/services/event_contract/backtest.py backend/tests/test_reviewer_learning_time_isolation.py
git commit -m "Isolate reviewer learning weights from backtest window (fix leakage)"
```

---

### Task 2: 显式零值生效 + 延迟默认 3 秒

**Files:**
- Modify: `backend/services/event_contract/config.py:56-61`
- Modify: `backend/api/event_contract_routes.py:83`（`delay_seconds` 默认 3）
- Test: `backend/tests/test_event_contract_config_defaults.py`

**Interfaces:**
- Produces: `_normalize_config` 对 `win_payout_ratio/fee_rate/slippage_bps/delay_seconds` 尊重显式 0；`delay_seconds` 缺省 3。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_config_defaults.py
"""Explicit zero economics must not be coerced back to defaults."""
from services.event_contract_service import event_contract_service


BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _norm(extra):
    return event_contract_service._normalize_config({**BASE, **extra}, prediction=False)


def test_explicit_zero_payout_kept():
    assert _norm({"win_payout_ratio": 0})["win_payout_ratio"] == 0


def test_explicit_zero_delay_kept():
    assert _norm({"delay_seconds": 0})["delay_seconds"] == 0


def test_delay_defaults_to_three_seconds():
    assert _norm({})["delay_seconds"] == 3


def test_payout_defaults_to_08():
    assert _norm({})["win_payout_ratio"] == 0.8
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_config_defaults.py -v`
Expected: `test_explicit_zero_payout_kept` 和 `test_delay_defaults_to_three_seconds` FAIL

- [ ] **Step 3: 实现**

`config.py` 中先在 `_normalize_config` 顶部加辅助（模块级函数，放文件末尾亦可）：

```python
def _number(config: Dict[str, Any], key: str, default: float) -> float:
    value = config.get(key)
    return float(value) if value is not None else float(default)
```

替换 cfg 四行：

```python
            "win_payout_ratio": _number(config, "win_payout_ratio", 0.8),
            "fee_rate": _number(config, "fee_rate", 0),
            "slippage_bps": _number(config, "slippage_bps", 0),
            "delay_seconds": int(_number(config, "delay_seconds", 3)),
```

`event_contract_routes.py` `BacktestRequest`：`delay_seconds: int = Field(default=3, ge=0)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_event_contract_config_defaults.py tests/test_event_contract_backtest.py -q`
Expected: passed（若既有测试假设 delay 默认 0，改其配置显式传 `"delay_seconds": 0`）

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/config.py backend/api/event_contract_routes.py backend/tests/test_event_contract_config_defaults.py
git commit -m "Respect explicit zero economics; default event backtest delay to 3s"
```

---

### Task 3: 行权基准价改为决策后 bar 开盘价

**Files:**
- Modify: `backend/services/event_contract/backtest_helpers.py`（新增 `_resolve_entry_bar`）
- Modify: `backend/services/event_contract/backtest.py:285-307,401-431`
- Test: `backend/tests/test_event_contract_entry_bar.py`

**Interfaces:**
- Produces: `_resolve_entry_bar(klines, decision_ts, delay_seconds, interval, max_entry_lag_seconds) -> tuple[Optional[int], int]`（返回 entry_idx 与 lag 秒；不可用返回 `(None, lag)`）。入场价 = `klines[entry_idx]["open"]`；结算基准时间 = `klines[entry_idx]["timestamp"]`；到期价 = 到期 bar 的 **open**。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_entry_bar.py
"""Strike must come from the first observable bar OPEN at/after the decision."""
from services.event_contract_service import event_contract_service


def _klines(start=1000, interval=60, count=10, open_base=100.0):
    return [
        {"timestamp": start + i * interval, "open": open_base + i, "high": 0, "low": 0,
         "close": open_base + i + 0.5, "volume": 1.0}
        for i in range(count)
    ]


def test_entry_bar_is_bar_opening_at_decision_ts():
    klines = _klines()
    # decision at close of bar 0 => decision_ts = 1060 = open ts of bar 1
    idx, lag = event_contract_service._resolve_entry_bar(klines, 1060, 3, 60, 60)
    assert idx == 1
    assert lag == 0
    assert klines[idx]["open"] == 101.0


def test_delay_longer_than_bar_advances_entry():
    klines = _klines()
    # delay 61s pushes target into bar 2 [1120, 1180)
    idx, _ = event_contract_service._resolve_entry_bar(klines, 1060, 61, 60, 120)
    assert idx == 2


def test_gap_exceeding_lag_tolerance_returns_none():
    klines = _klines()[:2] + _klines(start=1600, count=3)  # gap after bar 1
    idx, lag = event_contract_service._resolve_entry_bar(klines, 1120, 3, 60, 60)
    assert idx is None
    assert lag > 60
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_entry_bar.py -v`
Expected: FAIL（`_resolve_entry_bar` 不存在）

- [ ] **Step 3: 实现 helper**

`backtest_helpers.py` 末尾（`_apply_slippage` 后）加：

```python
    def _resolve_entry_bar(
        self,
        klines: List[Dict[str, Any]],
        decision_ts: int,
        delay_seconds: int,
        interval: int,
        max_entry_lag_seconds: int,
    ) -> "tuple[Optional[int], int]":
        """First observable strike bar at/after the decision.

        The strike is the OPEN of the bar containing decision_ts + delay.
        Returns (entry_idx, lag_seconds); lag is how much later than
        decision_ts the strike bar opens (0 for a contiguous series).
        """
        target_ts = decision_ts + max(0, int(delay_seconds))
        entry_idx = self._first_index_at_or_after(klines, decision_ts)
        if entry_idx is None:
            return None, 0
        while (
            entry_idx + 1 < len(klines)
            and klines[entry_idx]["timestamp"] + interval <= target_ts
        ):
            entry_idx += 1
        if entry_idx >= len(klines):
            return None, 0
        lag = int(klines[entry_idx]["timestamp"] - decision_ts)
        if lag > max_entry_lag_seconds:
            return None, lag
        return entry_idx, lag
```

- [ ] **Step 4: 接入回测循环**

`backtest.py` 用 helper 替换 285-297 的入场块：

```python
            entry_idx, entry_delay_lag = self._resolve_entry_bar(
                klines, decision_ts, cfg["delay_seconds"], interval, cfg["max_entry_lag_seconds"]
            )
            if entry_idx is None:
                skipped["entry_delay_skipped_count"] += 1
                continue
```

行 299-301 保持 `settlement_entry_ts = klines[entry_idx]["timestamp"]`、`expiry_ts = settlement_entry_ts + cfg["expiry_minutes"] * 60` 不变。
行 401-404 改为 open 对 open（精确 expiry_minutes 视界）：

```python
            raw_entry_price = klines[entry_idx]["open"]
            raw_expiry_price = klines[expiry_idx]["open"]
```

行 426-429 的 trade 记录改用 bar 开盘时间（真实下注/结算时刻）：

```python
                "entry_time": self._to_iso(klines[entry_idx]["timestamp"]),
                ...
                "expiry_time": self._to_iso(klines[expiry_idx]["timestamp"]),
```

同步改 315-325 `record_ai_trader_team_decisions` 的 `entry_time/expiry_time/entry_price/expiry_price` 为相同的 open 口径。

- [ ] **Step 5: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_entry_bar.py tests/test_event_contract_backtest.py -q`
Expected: passed（既有回测测试如断言 close 入场价需按新口径更新期望值——期望值改为对应 bar 的 open）

- [ ] **Step 6: Commit**

```bash
git add backend/services/event_contract/backtest_helpers.py backend/services/event_contract/backtest.py backend/tests/test_event_contract_entry_bar.py backend/tests/test_event_contract_backtest.py
git commit -m "Use next-bar open as event contract strike (kill same-print fill)"
```

---

### Task 4: TradeLog ORM 补列 + 幂等迁移

**Files:**
- Modify: `backend/database/models/event_contract.py:37-65`
- Create: `backend/database/migrations/add_event_contract_trade_log_ai_columns.py`
- Modify: `backend/database/migration_manager.py`（`MIGRATIONS` 列表末尾追加文件名）
- Test: `backend/tests/test_event_contract_trade_log_schema.py`

**Interfaces:**
- Produces: `EventContractTradeLog` 与 `data.py:_persist_backtest` 写入列一致。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_trade_log_schema.py
"""ORM must cover every column _persist_backtest writes."""
from database.models.event_contract import EventContractTradeLog

REQUIRED = {
    "consensus_source", "ai_participated", "ai_model", "ai_account_name",
    "signal_time", "signal_type", "event_signal",
    "entry_delay_lag_seconds", "expiry_lag_seconds",
}


def test_orm_has_all_persisted_columns():
    columns = {c.name for c in EventContractTradeLog.__table__.columns}
    missing = REQUIRED - columns
    assert not missing, f"ORM missing columns: {missing}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_trade_log_schema.py -v`
Expected: FAIL，列出 9 个缺失列

- [ ] **Step 3: 补 ORM 列**

`event_contract.py` 在 `ai_consensus_rate` 行后插入：

```python
    consensus_source = Column(String(30), nullable=True)
    ai_participated = Column(Boolean, nullable=False, default=False)
    ai_model = Column(String(100), nullable=True)
    ai_account_name = Column(String(100), nullable=True)
    signal_time = Column(TIMESTAMP, nullable=True)
    signal_type = Column(String(50), nullable=True)
    event_signal = Column(Text, nullable=True)
    entry_delay_lag_seconds = Column(Integer, nullable=False, default=0)
    expiry_lag_seconds = Column(Integer, nullable=False, default=0)
```

- [ ] **Step 4: 写幂等迁移**

```python
# backend/database/migrations/add_event_contract_trade_log_ai_columns.py
#!/usr/bin/env python3
"""Migration: add AI/timing columns to event_contract_trade_logs (idempotent)."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal

COLUMNS = {
    "consensus_source": "VARCHAR(30)",
    "ai_participated": "BOOLEAN NOT NULL DEFAULT FALSE",
    "ai_model": "VARCHAR(100)",
    "ai_account_name": "VARCHAR(100)",
    "signal_time": "TIMESTAMP",
    "signal_type": "VARCHAR(50)",
    "event_signal": "TEXT",
    "entry_delay_lag_seconds": "INTEGER NOT NULL DEFAULT 0",
    "expiry_lag_seconds": "INTEGER NOT NULL DEFAULT 0",
}


def _existing_columns(db) -> set:
    result = db.execute(text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'event_contract_trade_logs'
        """
    ))
    return {row[0] for row in result}


def upgrade() -> None:
    db = SessionLocal()
    try:
        existing = _existing_columns(db)
        for name, ddl in COLUMNS.items():
            if name in existing:
                continue
            db.execute(text(f"ALTER TABLE event_contract_trade_logs ADD COLUMN {name} {ddl}"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
```

`migration_manager.py`：在 `MIGRATIONS = [` 列表**末尾**追加 `"add_event_contract_trade_log_ai_columns.py",`。

- [ ] **Step 5: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_trade_log_schema.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/database/models/event_contract.py backend/database/migrations/add_event_contract_trade_log_ai_columns.py backend/database/migration_manager.py backend/tests/test_event_contract_trade_log_schema.py
git commit -m "Align EventContractTradeLog ORM with persisted columns + idempotent migration"
```

---

### Task 5: 平台预设 + 平局退款结算

**Files:**
- Create: `backend/services/event_contract/platforms.py`
- Modify: `backend/services/event_contract/config.py`（platform 合并 + 校验）
- Modify: `backend/services/event_contract/backtest_helpers.py:192-199`（refund）
- Modify: `backend/api/event_contract_routes.py`（BacktestRequest 加字段）
- Test: `backend/tests/test_event_contract_platforms.py`

**Interfaces:**
- Produces: `PLATFORM_PRESETS: dict`；`apply_platform_preset(config: dict) -> dict`；cfg 新键 `platform/min_stake/min_seconds_between_trades/daily_loss_cap`；`draw_result` 新增合法值 `"refund"`（结算返回 `"draw"`，pnl = -fee）。
- Consumes: Task 2 的 `_number`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_platforms.py
"""Platform presets must inject each venue's real rules."""
import pytest

from services.event_contract_service import event_contract_service

BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _norm(extra):
    return event_contract_service._normalize_config({**BASE, **extra}, prediction=False)


def test_binance_event_preset():
    cfg = _norm({"platform": "binance_event"})
    assert cfg["draw_result"] == "refund"
    assert cfg["win_payout_ratio"] == 0.8
    assert cfg["daily_loss_cap"] == 10000
    assert cfg["min_stake"] == 5


def test_hibt_preset_sets_trade_spacing():
    cfg = _norm({"platform": "hibt"})
    assert cfg["min_seconds_between_trades"] == 60
    assert cfg["min_stake"] == 3


def test_stake_below_platform_minimum_rejected():
    with pytest.raises(ValueError):
        _norm({"platform": "binance_event", "stake_amount": 4})


def test_user_override_survives_preset():
    cfg = _norm({"platform": "hibt", "win_payout_ratio": 0.85})
    assert cfg["win_payout_ratio"] == 0.85


def test_refund_draw_settles_as_draw():
    result = event_contract_service._settle_event_contract("long", 100.0, 100.0, "refund")
    assert result == "draw"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_platforms.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 platforms.py**

```python
# backend/services/event_contract/platforms.py
"""Venue presets for event-contract economics.

Sources (2026-07): HIBT support docs (payout 0.80, no fee, min 3 USDT,
per-minute open cap, settles on venue index mark price); Binance Event
Contracts FAQ (fixed payout ~0.80, draw refunds premium, min 5 USDT,
10k USDT daily loss cap, no extra fee).
"""
from __future__ import annotations

from typing import Any, Dict

PLATFORM_PRESETS: Dict[str, Dict[str, Any]] = {
    "hibt": {
        "win_payout_ratio": 0.8,
        "fee_rate": 0.0,
        "draw_result": "loss",
        "min_stake": 3.0,
        "min_seconds_between_trades": 60,
        "daily_loss_cap": None,
    },
    "binance_event": {
        "win_payout_ratio": 0.8,
        "fee_rate": 0.0,
        "draw_result": "refund",
        "min_stake": 5.0,
        "min_seconds_between_trades": 0,
        "daily_loss_cap": 10000.0,
    },
    "custom": {
        "min_stake": 1.0,
        "min_seconds_between_trades": 0,
        "daily_loss_cap": None,
    },
}

# Keys a preset may fill only when the user did not set them explicitly.
_SOFT_KEYS = ("win_payout_ratio", "fee_rate", "draw_result")
# Keys the platform always dictates.
_HARD_KEYS = ("min_stake", "min_seconds_between_trades", "daily_loss_cap")


def apply_platform_preset(config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge platform rules into a raw request config (pre-normalization)."""
    platform = str(config.get("platform") or "custom").lower()
    preset = PLATFORM_PRESETS.get(platform)
    if preset is None:
        raise ValueError(f"Unsupported platform: {platform}")
    merged = dict(config)
    merged["platform"] = platform
    for key in _SOFT_KEYS:
        if key in preset and merged.get(key) is None:
            merged[key] = preset[key]
    for key in _HARD_KEYS:
        merged[key] = preset.get(key, PLATFORM_PRESETS["custom"][key])
    return merged
```

`config.py` `_normalize_config` 开头（`now = ...` 之前）加：

```python
        from services.event_contract.platforms import apply_platform_preset
        config = apply_platform_preset(config)
```

cfg 字典加（`"draw_result"` 附近）：

```python
            "platform": config["platform"],
            "min_stake": float(config.get("min_stake") or 1.0),
            "min_seconds_between_trades": int(config.get("min_seconds_between_trades") or 0),
            "daily_loss_cap": float(config["daily_loss_cap"]) if config.get("daily_loss_cap") is not None else None,
```

`draw_result` 校验（文件末尾 clamp 区）：

```python
        if cfg["draw_result"] not in {"loss", "draw", "refund"}:
            raise ValueError(f"Unsupported draw_result: {cfg['draw_result']}")
        if cfg["stake_amount"] < cfg["min_stake"]:
            raise ValueError(
                f"stake_amount {cfg['stake_amount']} is below the {cfg['platform']} minimum {cfg['min_stake']}"
            )
```

注意：`draw_result` 原行 `str(config.get("draw_result") or "loss")` 会把预设注入的值原样带入，但用户显式传 `"loss"` 时 preset 不覆盖（`_SOFT_KEYS` 只在 None 时填充）——BacktestRequest 需把 `draw_result` 默认值改为 `None`（见 Step 4），否则 Pydantic 默认 `"loss"` 会永远挡住 preset。

`backtest_helpers.py` `_settle_event_contract` 首行改：

```python
        if expiry == entry:
            return "draw" if draw_result in ("draw", "refund") else "loss"
```

`event_contract_routes.py` `BacktestRequest` 增改字段：

```python
    platform: str = Field(default="custom", pattern="^(hibt|binance_event|custom)$")
    draw_result: Optional[str] = Field(default=None, pattern="^(loss|draw|refund)$")
    win_payout_ratio: Optional[float] = Field(default=None, ge=0)
    fee_rate: Optional[float] = Field(default=None, ge=0)
```

（payout/fee 改 Optional，None 时由 preset/默认值决定——Task 2 的 `_number` 已兼容 None。）

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_platforms.py tests/test_event_contract_config_defaults.py -v`
Expected: passed（`test_payout_defaults_to_08` 仍过：custom 平台不注入 payout，走 `_number` 默认 0.8）

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/platforms.py backend/services/event_contract/config.py backend/services/event_contract/backtest_helpers.py backend/api/event_contract_routes.py backend/tests/test_event_contract_platforms.py
git commit -m "Add HIBT/Binance event-contract platform presets with refund draws"
```

---

### Task 6: 交易约束（非重叠 / 频率 / 日亏上限）

**Files:**
- Create: `backend/services/event_contract/backtest_constraints.py`
- Modify: `backend/services/event_contract/config.py`（`non_overlapping_only` 默认 True）
- Modify: `backend/services/event_contract/backtest.py`（循环接入 + skipped 计数）
- Modify: `backend/api/event_contract_routes.py`（`non_overlapping_only: bool = True`）
- Test: `backend/tests/test_event_contract_constraints.py`

**Interfaces:**
- Produces:

```python
class TradeConstraintTracker:
    def __init__(self, *, non_overlapping: bool, min_seconds_between_trades: int, daily_loss_cap: Optional[float]) -> None: ...
    def allow(self, decision_ts: int) -> Optional[str]:  # None=allowed, else skip reason key
    def record(self, entry_ts: int, settlement_ts: int, pnl: float) -> None: ...
```

skip reason keys：`"overlap_skipped_count" | "frequency_skipped_count" | "daily_cap_skipped_count"`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_constraints.py
"""Non-overlap, spacing and daily-loss-cap constraints."""
from services.event_contract.backtest_constraints import TradeConstraintTracker

DAY = 86400


def _tracker(**kw):
    defaults = {"non_overlapping": True, "min_seconds_between_trades": 0, "daily_loss_cap": None}
    return TradeConstraintTracker(**{**defaults, **kw})


def test_overlap_blocked_until_settlement():
    t = _tracker()
    assert t.allow(1000) is None
    t.record(entry_ts=1000, settlement_ts=1300, pnl=0.0)
    assert t.allow(1200) == "overlap_skipped_count"
    assert t.allow(1300) is None


def test_min_spacing():
    t = _tracker(non_overlapping=False, min_seconds_between_trades=60)
    t.record(entry_ts=1000, settlement_ts=1300, pnl=0.0)
    assert t.allow(1030) == "frequency_skipped_count"
    assert t.allow(1060) is None


def test_daily_loss_cap_blocks_same_utc_day_only():
    t = _tracker(daily_loss_cap=100.0)
    t.record(entry_ts=1000, settlement_ts=1300, pnl=-100.0)
    assert t.allow(2000) == "daily_cap_skipped_count"
    assert t.allow(1000 + DAY) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_constraints.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# backend/services/event_contract/backtest_constraints.py
"""Execution-realism constraints for the event-contract backtest loop."""
from __future__ import annotations

from typing import Optional


class TradeConstraintTracker:
    """Tracks open exposure, trade spacing and venue daily-loss caps."""

    def __init__(
        self,
        *,
        non_overlapping: bool,
        min_seconds_between_trades: int,
        daily_loss_cap: Optional[float],
    ) -> None:
        self.non_overlapping = non_overlapping
        self.min_spacing = max(0, int(min_seconds_between_trades))
        self.daily_loss_cap = daily_loss_cap
        self._open_until: Optional[int] = None
        self._last_entry_ts: Optional[int] = None
        self._loss_day: Optional[int] = None
        self._loss_today = 0.0

    def allow(self, decision_ts: int) -> Optional[str]:
        if self.non_overlapping and self._open_until is not None and decision_ts < self._open_until:
            return "overlap_skipped_count"
        if (
            self.min_spacing
            and self._last_entry_ts is not None
            and decision_ts - self._last_entry_ts < self.min_spacing
        ):
            return "frequency_skipped_count"
        if self.daily_loss_cap is not None and self._loss_day == decision_ts // 86400:
            if self._loss_today >= self.daily_loss_cap:
                return "daily_cap_skipped_count"
        return None

    def record(self, entry_ts: int, settlement_ts: int, pnl: float) -> None:
        self._open_until = settlement_ts
        self._last_entry_ts = entry_ts
        if pnl < 0:
            day = entry_ts // 86400
            if day != self._loss_day:
                self._loss_day = day
                self._loss_today = 0.0
            self._loss_today += -pnl
```

`config.py` cfg 加：

```python
            "non_overlapping_only": bool(config.get("non_overlapping_only", True)),
```

`backtest.py` 接入：初始化区（`ai_trader_team_state = ...` 后）：

```python
        from services.event_contract.backtest_constraints import TradeConstraintTracker
        constraints = TradeConstraintTracker(
            non_overlapping=cfg["non_overlapping_only"],
            min_seconds_between_trades=cfg["min_seconds_between_trades"],
            daily_loss_cap=cfg["daily_loss_cap"],
        )
```

`skipped` 字典加三个键（初值 0）：`"overlap_skipped_count"`, `"frequency_skipped_count"`, `"daily_cap_skipped_count"`。
循环内，在 `direction not in ("long", "short")` 检查之后、结算之前：

```python
            constraint_reason = constraints.allow(decision_ts)
            if constraint_reason:
                skipped[constraint_reason] += 1
                continue
```

结算后（`trades.append(trade)` 之前）：

```python
            constraints.record(
                entry_ts=klines[entry_idx]["timestamp"],
                settlement_ts=klines[expiry_idx]["timestamp"],
                pnl=pnl,
            )
```

`event_contract_routes.py` `BacktestRequest` 加 `non_overlapping_only: bool = True`。

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_constraints.py tests/test_event_contract_backtest.py -q`
Expected: passed（既有回测测试若因非重叠默认 On 而交易数变少，为其配置显式传 `"non_overlapping_only": False` 保持旧断言）

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/backtest_constraints.py backend/services/event_contract/config.py backend/services/event_contract/backtest.py backend/api/event_contract_routes.py backend/tests/test_event_contract_constraints.py
git commit -m "Enforce non-overlap, trade spacing and daily loss cap in event backtest"
```

---

### Task 7: 统计模块（Wilson CI + 显著性 + 结算敏感度 + 严格达标）

**Files:**
- Create: `backend/services/event_contract/backtest_stats.py`
- Modify: `backend/services/event_contract/backtest_helpers.py:55-58,71-113`（summary 接线）
- Test: `backend/tests/test_event_contract_stats.py`

**Interfaces:**
- Produces:

```python
def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]  # 0-100 百分数
def binomial_p_value(wins: int, n: int, p0: float) -> float  # 单侧 P(X >= wins | p0)，p0 为 0-1
def settlement_sensitivity(trades: list[dict], bps_levels=(2, 5, 10)) -> dict  # {"bps_2": 翻转%, ...}
```

- summary 新键：`win_rate_ci_low/win_rate_ci_high/decided_trades/p_value_vs_breakeven/significant_vs_breakeven/settlement_sensitivity/target_win_rate_status`；`target_win_rate_met` 重定义为 CI 下界过盈亏平衡线。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_stats.py
"""Wilson CI, binomial significance and settlement sensitivity."""
from services.event_contract.backtest_stats import (
    binomial_p_value,
    settlement_sensitivity,
    wilson_interval,
)


def test_wilson_interval_known_value():
    lo, hi = wilson_interval(24, 30)
    assert 62.0 < lo < 64.0
    assert 90.0 < hi < 91.0


def test_wilson_empty_sample():
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_binomial_p_value_extremes():
    # 30/30 wins vs p0=0.5556 is overwhelming evidence
    assert binomial_p_value(30, 30, 0.5556) < 1e-6
    # 5/10 wins vs 0.5556 is not significant
    assert binomial_p_value(5, 10, 0.5556) > 0.05


def _trade(entry, expiry, direction="long"):
    result = "win" if (expiry > entry) == (direction == "long") and expiry != entry else ("draw" if expiry == entry else "loss")
    return {"entry_price": entry, "expiry_price": expiry, "direction": direction, "result": result}


def test_settlement_sensitivity_counts_flips():
    # 1bp winning margin: flips at 2bps shift; 100bp margin: never flips
    trades = [_trade(100.0, 100.01), _trade(100.0, 101.0)]
    report = settlement_sensitivity(trades)
    assert report["bps_2"] == 50.0
    assert report["bps_10"] == 50.0
    assert report["trades_evaluated"] == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_stats.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# backend/services/event_contract/backtest_stats.py
"""Statistical credibility helpers for event-contract backtests."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple


def wilson_interval(wins: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score 95% interval, returned in percent (0-100)."""
    if n <= 0:
        return 0.0, 0.0
    phat = wins / n
    z2 = z * z
    denom = 1 + z2 / n
    center = phat + z2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    lo = max(0.0, (center - margin) / denom)
    hi = min(1.0, (center + margin) / denom)
    return round(lo * 100, 2), round(hi * 100, 2)


def binomial_p_value(wins: int, n: int, p0: float) -> float:
    """One-sided exact binomial tail P(X >= wins | n, p0)."""
    if n <= 0:
        return 1.0
    p0 = min(max(p0, 0.0), 1.0)
    tail = 0.0
    for k in range(wins, n + 1):
        tail += math.comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
    return min(1.0, max(0.0, tail))


def _settles_win(direction: str, entry: float, expiry: float) -> Any:
    """True=win, False=loss, None=draw for a shifted settlement print."""
    if expiry == entry:
        return None
    if direction == "long":
        return expiry > entry
    return expiry < entry


def settlement_sensitivity(
    trades: List[Dict[str, Any]], bps_levels: Sequence[int] = (2, 5, 10)
) -> Dict[str, Any]:
    """% of decided trades whose outcome flips if the venue settlement print
    differs from our kline source by +/- N bps."""
    decided = [t for t in trades if t.get("result") in ("win", "loss")]
    report: Dict[str, Any] = {"trades_evaluated": len(decided)}
    for bps in bps_levels:
        if not decided:
            report[f"bps_{bps}"] = 0.0
            continue
        flips = 0
        shift = bps / 10000.0
        for trade in decided:
            entry = float(trade["entry_price"])
            expiry = float(trade["expiry_price"])
            direction = str(trade["direction"])
            base = trade["result"] == "win"
            for factor in (1 + shift, 1 - shift):
                outcome = _settles_win(direction, entry, expiry * factor)
                if outcome is None or outcome != base:
                    flips += 1
                    break
        report[f"bps_{bps}"] = round(flips / len(decided) * 100, 2)
    return report
```

`backtest_helpers.py` 接线——`_build_summary` 中替换 55-58 行并在 summary 构建后追加键：

```python
        from services.event_contract.backtest_stats import (
            binomial_p_value,
            settlement_sensitivity,
            wilson_interval,
        )
        decided = wins + losses
        win_rate = round(wins / total * 100, 2) if total else 0
        decided_win_rate = round(wins / decided * 100, 2) if decided else 0
        ci_low, ci_high = wilson_interval(wins, decided)
        p_value = binomial_p_value(wins, decided, break_even_win_rate / 100)
        target_min_trades = int(cfg.get("target_min_trades", 10))
        target_sample_met = decided >= target_min_trades
        if not target_sample_met:
            target_status = "insufficient_sample"
        elif ci_low >= break_even_win_rate and decided_win_rate >= target_win_rate and not partial:
            target_status = "met"
        else:
            target_status = "not_met"
        target_win_rate_met = target_status == "met"
```

summary 字典加键（`"break_even_win_rate"` 行后）：

```python
            "decided_trades": decided,
            "decided_win_rate": decided_win_rate,
            "win_rate_ci_low": ci_low,
            "win_rate_ci_high": ci_high,
            "p_value_vs_breakeven": round(p_value, 6),
            "significant_vs_breakeven": bool(decided and p_value < 0.05),
            "target_win_rate_status": target_status,
            "settlement_sensitivity": settlement_sensitivity(trades),
```

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_stats.py tests/test_event_contract_backtest.py -q`
Expected: passed（既有测试断言 `target_win_rate_met` 的小样本用例按新语义更新为 `target_win_rate_status == "insufficient_sample"`）

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/backtest_stats.py backend/services/event_contract/backtest_helpers.py backend/tests/test_event_contract_stats.py
git commit -m "Add Wilson CI, breakeven significance and settlement sensitivity to summary"
```

---

### Task 8: 块自助法蒙特卡洛

**Files:**
- Modify: `backend/services/event_contract/backtest_validation.py:114-141`
- Modify: `backend/services/event_contract/backtest_helpers.py:121-127`（传 cfg 已有，无需改——`build_backtest_validation_report` 已收 cfg）
- Test: `backend/tests/test_event_contract_block_bootstrap.py`

**Interfaces:**
- Produces: `_monte_carlo_report(trades, cfg, simulations=200)` 输出增加 `"method": "iid"|"block"` 与 `"block_length": int`。重叠模式（`non_overlapping_only=False`）用移动块自助法，块长 = `max(1, ceil(expiry_minutes*60 / PERIOD_SECONDS[period]))`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_block_bootstrap.py
"""Overlapping trades must use block bootstrap, not iid resampling."""
from services.event_contract.backtest_validation import _monte_carlo_report


def _trades(n=40):
    return [{"profit_loss": 80.0 if i % 3 else -100.0} for i in range(n)]


CFG_OVERLAP = {"non_overlapping_only": False, "expiry_minutes": 5, "period": "1m"}
CFG_CLEAN = {"non_overlapping_only": True, "expiry_minutes": 5, "period": "1m"}


def test_block_method_selected_for_overlapping():
    report = _monte_carlo_report(_trades(), CFG_OVERLAP)
    assert report["method"] == "block"
    assert report["block_length"] == 5


def test_iid_method_for_non_overlapping():
    report = _monte_carlo_report(_trades(), CFG_CLEAN)
    assert report["method"] == "iid"


def test_deterministic_with_seed():
    a = _monte_carlo_report(_trades(), CFG_OVERLAP)
    b = _monte_carlo_report(_trades(), CFG_OVERLAP)
    assert a == b
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_block_bootstrap.py -v`
Expected: FAIL（签名不符）

- [ ] **Step 3: 实现**

`backtest_validation.py` 顶部加 `from services.event_contract.constants import PERIOD_SECONDS`，替换 `_monte_carlo_report`：

```python
def _monte_carlo_report(
    trades: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    simulations: int = MONTE_CARLO_SIMULATIONS,
) -> Dict[str, Any]:
    pnls = [float(trade.get("profit_loss") or 0.0) for trade in trades]
    non_overlapping = bool(cfg.get("non_overlapping_only", True))
    interval = PERIOD_SECONDS.get(str(cfg.get("period") or "1m"), 60)
    block_length = max(1, math.ceil(int(cfg.get("expiry_minutes") or 5) * 60 / interval))
    method = "iid" if non_overlapping else "block"
    if not pnls:
        return {
            "simulations": 0, "method": method, "block_length": block_length,
            "profitable_ratio": 0.0, "p5_pnl": 0.0, "p50_pnl": 0.0, "p95_pnl": 0.0,
            "max_drawdown_p95": 0.0,
        }

    rng = random.Random(MONTE_CARLO_SEED)
    totals: List[float] = []
    drawdowns: List[float] = []
    for _ in range(simulations):
        if method == "iid" or block_length >= len(pnls):
            sampled = [rng.choice(pnls) for _ in pnls]
        else:
            sampled = []
            while len(sampled) < len(pnls):
                start = rng.randrange(0, len(pnls) - block_length + 1)
                sampled.extend(pnls[start : start + block_length])
            sampled = sampled[: len(pnls)]
        totals.append(round(sum(sampled), 4))
        drawdowns.append(round(_max_drawdown_from_pnls(sampled), 4))

    return {
        "simulations": simulations,
        "method": method,
        "block_length": block_length,
        "profitable_ratio": round(sum(1 for total in totals if total > 0) / simulations * 100, 2),
        "p5_pnl": round(_percentile(totals, 5), 4),
        "p50_pnl": round(_percentile(totals, 50), 4),
        "p95_pnl": round(_percentile(totals, 95), 4),
        "max_drawdown_p95": round(_percentile(drawdowns, 95), 4),
    }
```

调用点 `build_backtest_validation_report` 内改：`monte_carlo = _monte_carlo_report(trades, cfg)`。

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_block_bootstrap.py tests/test_event_contract_backtest.py -q`
Expected: passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/backtest_validation.py backend/tests/test_event_contract_block_bootstrap.py
git commit -m "Use block bootstrap for overlapping event-contract trade streams"
```

---

### Task 9: 概率校准报告

**Files:**
- Modify: `backend/services/event_contract/backtest_stats.py`（加 `calibration_report`）
- Modify: `backend/services/event_contract/backtest_helpers.py`（summary 接线）
- Test: `backend/tests/test_event_contract_calibration.py`

**Interfaces:**
- Produces: `calibration_report(trades, min_samples=50) -> dict`。预测概率取 `trade["event_signal"]["expected_win_rate"]`（0-100）；输出 `{"status": "ok"|"insufficient_sample", "brier_score": float, "buckets": [{"range": "65-75", "n": int, "predicted_avg": float, "actual_win_rate": float}]}`，仅统计 decided（win/loss）交易。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_calibration.py
"""Predicted expected_win_rate must be scored against realized outcomes."""
from services.event_contract.backtest_stats import calibration_report


def _trade(predicted, won):
    return {
        "result": "win" if won else "loss",
        "event_signal": {"expected_win_rate": predicted},
    }


def test_insufficient_sample():
    assert calibration_report([_trade(75, True)] * 10)["status"] == "insufficient_sample"


def test_perfect_calibration_bucket():
    trades = [_trade(80, i < 40) for i in range(50)]  # 80% predicted, 80% realized
    report = calibration_report(trades, min_samples=50)
    assert report["status"] == "ok"
    bucket = next(b for b in report["buckets"] if b["n"] == 50)
    assert bucket["actual_win_rate"] == 80.0
    assert abs(report["brier_score"] - (0.8 * 0.2)) < 0.01  # p(1-p) for perfect calibration
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_calibration.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backtest_stats.py` 追加：

```python
CALIBRATION_BUCKETS = ((0, 55), (55, 65), (65, 75), (75, 85), (85, 101))


def calibration_report(trades: List[Dict[str, Any]], min_samples: int = 50) -> Dict[str, Any]:
    """Reliability table + Brier score of predicted expected_win_rate."""
    samples = []
    for trade in trades:
        if trade.get("result") not in ("win", "loss"):
            continue
        predicted = ((trade.get("event_signal") or {}).get("expected_win_rate"))
        if predicted is None:
            continue
        samples.append((float(predicted) / 100.0, 1.0 if trade["result"] == "win" else 0.0))
    if len(samples) < min_samples:
        return {"status": "insufficient_sample", "n": len(samples), "min_samples": min_samples}

    brier = sum((p - y) ** 2 for p, y in samples) / len(samples)
    buckets = []
    for lo, hi in CALIBRATION_BUCKETS:
        rows = [(p, y) for p, y in samples if lo <= p * 100 < hi]
        if not rows:
            continue
        buckets.append(
            {
                "range": f"{lo}-{min(hi, 100)}",
                "n": len(rows),
                "predicted_avg": round(sum(p for p, _ in rows) / len(rows) * 100, 2),
                "actual_win_rate": round(sum(y for _, y in rows) / len(rows) * 100, 2),
            }
        )
    return {"status": "ok", "n": len(samples), "brier_score": round(brier, 4), "buckets": buckets}
```

`backtest_helpers.py` summary 追加键（`"settlement_sensitivity"` 行后）：

```python
            "calibration_report": calibration_report(trades),
```

（import 行加 `calibration_report`。）

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_calibration.py -q`
Expected: passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/backtest_stats.py backend/services/event_contract/backtest_helpers.py backend/tests/test_event_contract_calibration.py
git commit -m "Score predicted win probabilities with reliability buckets and Brier"
```

---

### Task 10: 策略指纹 + 一键冻结参数验证（holdout）

**Files:**
- Modify: `backend/services/event_contract/quality.py`（加 `_strategy_fingerprint`）
- Modify: `backend/services/event_contract/backtest_helpers.py`（summary 加 `strategy_fingerprint` 与 `platform`）
- Modify: `backend/api/event_contract_routes.py`（holdout 端点）
- Test: `backend/tests/test_event_contract_fingerprint.py`

**Interfaces:**
- Produces: `_strategy_fingerprint(cfg) -> str`（16 位 sha256，排除 `start_time/end_time`）；`POST /api/event-contract/backtest/{run_id}/holdout` body `{"start_time": iso, "end_time": iso}` → 复用原 run 的 config、覆盖窗口后创建新任务，返回任务 dict + `{"source_run_id", "strategy_fingerprint"}`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_event_contract_fingerprint.py
"""Strategy fingerprint must ignore the time window, nothing else."""
from services.event_contract_service import event_contract_service

BASE = {
    "symbol": "BTC",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-01-02T00:00:00Z",
}


def _fp(extra):
    cfg = event_contract_service._normalize_config({**BASE, **extra}, prediction=False)
    return event_contract_service._strategy_fingerprint(cfg)


def test_window_change_keeps_fingerprint():
    assert _fp({}) == _fp({"start_time": "2026-03-01T00:00:00Z", "end_time": "2026-03-02T00:00:00Z"})


def test_parameter_change_changes_fingerprint():
    assert _fp({}) != _fp({"enable_trap_filter": False})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_event_contract_fingerprint.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`quality.py` `_config_hash` 后加：

```python
    def _strategy_fingerprint(self, cfg: Dict[str, Any]) -> str:
        """Config hash that ignores the tested window - two runs with the same
        fingerprint on different windows form an honest out-of-sample pair."""
        public_cfg = self._public_config(cfg)
        for key in ("start_time", "end_time"):
            public_cfg.pop(key, None)
        payload = json.dumps(public_cfg, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

`backtest_helpers.py` summary 加键（`"config_hash"` 行后）：

```python
            "strategy_fingerprint": self._strategy_fingerprint(cfg),
            "platform": cfg.get("platform", "custom"),
            "non_overlapping_only": cfg.get("non_overlapping_only", True),
            "reviewer_weights_mode": cfg.get("reviewer_weights_mode", "pre_window"),
```

`event_contract_routes.py` 加端点（`pause_backtest_task` 后）：

```python
class HoldoutRequest(BaseModel):
    start_time: str
    end_time: str


@router.post("/backtest/{run_id}/holdout")
def create_holdout_task(run_id: int, payload: HoldoutRequest, request: Request, db: Session = Depends(get_db)):
    """Re-run a stored config on a fresh window (frozen-parameter OOS check)."""
    try:
        import json as _json
        from sqlalchemy import text as _text
        row = db.execute(
            _text("SELECT config, summary FROM event_contract_backtest_runs WHERE id = :id"),
            {"id": run_id},
        ).first()
        if not row:
            raise ValueError(f"Backtest run {run_id} not found")
        config = _json.loads(row[0] or "{}")
        config["start_time"] = payload.start_time
        config["end_time"] = payload.end_time
        config.pop("reviewer_weights", None)
        task = create_event_backtest_task(db, config=config, user_id=_current_user_id(request, db))
        start_event_backtest_task_thread(task["task_id"])
        summary = _json.loads(row[1] or "{}")
        task["source_run_id"] = run_id
        task["strategy_fingerprint"] = summary.get("strategy_fingerprint")
        return task
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Holdout task failed to start: {exc}")
```

注意路由顺序：该端点必须注册在 `GET /backtest/{run_id}` 之前无冲突（POST vs GET 方法不同，无需移动）。

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_event_contract_fingerprint.py tests/test_event_contract_backtest_tasks.py -q`
Expected: passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/event_contract/quality.py backend/services/event_contract/backtest_helpers.py backend/api/event_contract_routes.py backend/tests/test_event_contract_fingerprint.py
git commit -m "Add strategy fingerprint and frozen-parameter holdout endpoint"
```

---

### Task 11: 前端类型、默认值与平台选择器

**Files:**
- Modify: `frontend/app/lib/eventContractApi.ts`（类型 + holdout API）
- Modify: `frontend/app/components/backtest/types.ts`（FormState）
- Modify: `frontend/app/components/backtest/BacktestTool.tsx`（默认值 + payload + 平台联动）
- Modify: `frontend/app/components/backtest/BacktestConfigPanel.tsx`（平台选择器）
- Modify: `frontend/app/locales/en.json`, `frontend/app/locales/zh.json`

**Interfaces:**
- Produces: `FormState` 新增 `platform: 'hibt' | 'binance_event' | 'custom'`、`non_overlapping_only: boolean`；`EventContractBacktestConfig` 新增同名字段；`EventBacktestSummary` 新增 Task 7/9/10 的键；`createEventContractHoldoutTask(runId, {start_time, end_time})`。
- Consumes: Task 5/6/7/9/10 的后端字段。

- [ ] **Step 1: eventContractApi.ts 类型与 API**

`EventContractBacktestConfig` 接口加：

```typescript
  platform?: 'hibt' | 'binance_event' | 'custom'
  non_overlapping_only?: boolean
```

`EventBacktestSummary` 接口加：

```typescript
  decided_trades?: number
  decided_win_rate?: number
  win_rate_ci_low?: number
  win_rate_ci_high?: number
  p_value_vs_breakeven?: number
  significant_vs_breakeven?: boolean
  target_win_rate_status?: 'met' | 'not_met' | 'insufficient_sample'
  settlement_sensitivity?: { trades_evaluated: number; bps_2: number; bps_5: number; bps_10: number }
  calibration_report?: {
    status: 'ok' | 'insufficient_sample'
    n: number
    brier_score?: number
    buckets?: { range: string; n: number; predicted_avg: number; actual_win_rate: number }[]
  }
  strategy_fingerprint?: string
  platform?: string
  non_overlapping_only?: boolean
  overlap_skipped_count?: number
  frequency_skipped_count?: number
  daily_cap_skipped_count?: number
```

文件末尾加：

```typescript
export async function createEventContractHoldoutTask(
  runId: number,
  window: { start_time: string; end_time: string },
): Promise<EventBacktestTaskStatus & { source_run_id?: number; strategy_fingerprint?: string }> {
  return apiRequest(`/event-contract/backtest/${runId}/holdout`, {
    method: 'POST',
    body: JSON.stringify(window),
  })
}
```

（若该文件的既有函数用其他 helper 发请求，跟随现有写法。）确认 `frontend/app/lib/api.ts` barrel 已 re-export `eventContractApi`（已有），新函数自动可用。

- [ ] **Step 2: types.ts + BacktestTool.tsx 默认值**

`types.ts` `FormState` 加：

```typescript
  platform: 'hibt' | 'binance_event' | 'custom'
  non_overlapping_only: boolean
```

文件加平台预设常量：

```typescript
export const PLATFORM_FORM_PRESETS: Record<string, Partial<FormState>> = {
  hibt: { win_payout_ratio: 0.8, fee_rate: 0, draw_result: 'loss' },
  binance_event: { win_payout_ratio: 0.8, fee_rate: 0, draw_result: 'refund' },
  custom: {},
}
```

`BacktestTool.tsx` `buildDefaultForm` 改：`delay_seconds: 3`，并加 `platform: 'custom' as const`, `non_overlapping_only: true`。
`updateForm` 中加平台联动（`decision_policy` 分支旁）：

```typescript
      if (key === 'platform') {
        Object.assign(next, PLATFORM_FORM_PRESETS[value as string] || {})
      }
```

（import `PLATFORM_FORM_PRESETS`。）
`buildBacktestPayload` 加：

```typescript
    platform: form.platform,
    non_overlapping_only: form.non_overlapping_only,
```

- [ ] **Step 3: BacktestConfigPanel.tsx 平台选择器**

经济参数 grid（Initial Balance 之前）加：

```tsx
          <div className="space-y-1 col-span-2">
            <Label className="text-xs">{t('backtestTool.platform', 'Target Platform')}</Label>
            <Select value={form.platform} onValueChange={value => updateForm('platform', value as FormState['platform'])}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="custom">{t('backtestTool.platformCustom', 'Custom rules')}</SelectItem>
                <SelectItem value="hibt">{t('backtestTool.platformHibt', 'HIBT event contract')}</SelectItem>
                <SelectItem value="binance_event">{t('backtestTool.platformBinance', 'Binance Event Contracts')}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              {form.platform === 'binance_event'
                ? t('backtestTool.platformBinanceHint', 'Payout 0.8, draw refunds stake, min 5 USDT, 10k daily loss cap.')
                : form.platform === 'hibt'
                  ? t('backtestTool.platformHibtHint', 'Payout 0.8, no fee, min 3 USDT, one entry per minute.')
                  : t('backtestTool.platformCustomHint', 'All economics editable below.')}
            </p>
          </div>
```

Toggles 区加非重叠开关（第一个 ToggleRow 之前）：

```tsx
          <ToggleRow label={t('backtestTool.nonOverlapping', 'One bet at a time (independent samples)')} checked={form.non_overlapping_only} onChange={value => updateForm('non_overlapping_only', value)} />
```

- [ ] **Step 4: i18n**

`en.json` `backtestTool` 组加（保持 JSON 逗号正确）：

```json
"platform": "Target Platform",
"platformCustom": "Custom rules",
"platformHibt": "HIBT event contract",
"platformBinance": "Binance Event Contracts",
"platformBinanceHint": "Payout 0.8, draw refunds stake, min 5 USDT, 10k daily loss cap.",
"platformHibtHint": "Payout 0.8, no fee, min 3 USDT, one entry per minute.",
"platformCustomHint": "All economics editable below.",
"nonOverlapping": "One bet at a time (independent samples)"
```

`zh.json` 对应：

```json
"platform": "目标平台",
"platformCustom": "自定义规则",
"platformHibt": "HIBT 事件合约",
"platformBinance": "币安事件合约",
"platformBinanceHint": "赔付 0.8，平局退本金，最低 5 USDT，单日亏损上限 1 万。",
"platformHibtHint": "赔付 0.8，无手续费，最低 3 USDT，每分钟限一单。",
"platformCustomHint": "以下经济参数全部可手动编辑。",
"nonOverlapping": "同时只押一注（保证样本独立）"
```

注意 `FormState` 现有 `draw_result: string` 字段（值 `loss/draw/refund`）——`PLATFORM_FORM_PRESETS` 已用它。

- [ ] **Step 5: 构建验证**

Run: `pnpm build:frontend`
Expected: 构建成功，无 TS 错误

- [ ] **Step 6: Commit**

```bash
git add frontend/app/lib/eventContractApi.ts frontend/app/components/backtest/types.ts frontend/app/components/backtest/BacktestTool.tsx frontend/app/components/backtest/BacktestConfigPanel.tsx frontend/app/locales/en.json frontend/app/locales/zh.json
git commit -m "Add platform presets and non-overlap toggle to Backtest Tool UI"
```

---

### Task 12: 可信度卡片 + 冻结参数验证按钮

**Files:**
- Create: `frontend/app/components/backtest/CredibilityCard.tsx`
- Modify: `frontend/app/components/backtest/BacktestResultsPanel.tsx`（顶部渲染卡片）
- Modify: `frontend/app/components/backtest/BacktestTool.tsx`（holdout 按钮 + 任务启动）
- Modify: `frontend/app/locales/en.json`, `frontend/app/locales/zh.json`

**Interfaces:**
- Consumes: `EventBacktestSummary` 的 Task 11 新字段；`createEventContractHoldoutTask`。
- Produces: `<CredibilityCard summary={summary} onHoldout={...} holdoutRunning={boolean} />`。

- [ ] **Step 1: 实现 CredibilityCard**

```tsx
// frontend/app/components/backtest/CredibilityCard.tsx
import { useTranslation } from 'react-i18next'
import { FlaskConical, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { EventBacktestSummary } from '@/lib/api'

type Props = {
  summary: EventBacktestSummary
  onHoldout: () => void
  holdoutRunning: boolean
}

function sampleTone(n: number): 'red' | 'yellow' | 'green' {
  if (n < 30) return 'red'
  if (n < 100) return 'yellow'
  return 'green'
}

const TONE_CLASS: Record<string, string> = {
  red: 'bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/40',
  yellow: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 border-yellow-500/40',
  green: 'bg-green-500/10 text-green-700 dark:text-green-300 border-green-500/40',
}

export function CredibilityCard({ summary, onHoldout, holdoutRunning }: Props) {
  const { t } = useTranslation()
  const decided = summary.decided_trades ?? 0
  const tone = sampleTone(decided)
  const ciLow = summary.win_rate_ci_low ?? 0
  const ciHigh = summary.win_rate_ci_high ?? 0
  const breakeven = summary.break_even_win_rate ?? 55.56
  const significant = summary.significant_vs_breakeven === true
  const sensitivity = summary.settlement_sensitivity
  const calibration = summary.calibration_report

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{t('backtestTool.credibility', 'Credibility')}</CardTitle>
          <Button size="sm" variant="outline" onClick={onHoldout} disabled={holdoutRunning}>
            {holdoutRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
            {t('backtestTool.holdoutRun', 'Verify on new window')}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-md border px-2 py-0.5 text-xs ${TONE_CLASS[tone]}`}>
            {t('backtestTool.sampleSize', '{{count}} decided trades', { count: decided })}
          </span>
          <Badge variant="outline">
            {t('backtestTool.winRateCi', 'Win rate 95% CI: {{low}}%–{{high}}%', { low: ciLow, high: ciHigh })}
          </Badge>
          <Badge variant={significant ? 'default' : 'secondary'}>
            {significant
              ? t('backtestTool.significant', 'Beats breakeven {{be}}% (p={{p}})', { be: breakeven, p: summary.p_value_vs_breakeven })
              : t('backtestTool.notSignificant', 'Not proven above breakeven {{be}}%', { be: breakeven })}
          </Badge>
          {summary.target_win_rate_status === 'insufficient_sample' && (
            <Badge variant="secondary">{t('backtestTool.insufficientSample', 'Sample too small to judge')}</Badge>
          )}
        </div>
        {sensitivity && (
          <p className="text-xs text-muted-foreground">
            {t('backtestTool.sensitivity', 'Settlement sensitivity: {{b2}}% of results flip at ±2bps, {{b5}}% at ±5bps, {{b10}}% at ±10bps.', {
              b2: sensitivity.bps_2, b5: sensitivity.bps_5, b10: sensitivity.bps_10,
            })}
          </p>
        )}
        {calibration?.status === 'ok' && calibration.buckets && (
          <div className="text-xs">
            <span className="text-muted-foreground">
              {t('backtestTool.calibration', 'Calibration (Brier {{score}}):', { score: calibration.brier_score })}
            </span>
            <div className="mt-1 grid grid-cols-2 gap-1 sm:grid-cols-4">
              {calibration.buckets.map(bucket => (
                <div key={bucket.range} className="rounded border px-2 py-1">
                  {t('backtestTool.calibrationBucket', 'Predicted {{range}}% → actual {{actual}}% (n={{n}})', {
                    range: bucket.range, actual: bucket.actual_win_rate, n: bucket.n,
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 2: 接入 BacktestResultsPanel**

`BacktestResultsPanel.tsx`：Props 加 `onHoldout: () => void` 与 `holdoutRunning: boolean`；在结果 summary 存在时于面板最顶部渲染：

```tsx
{backtest?.summary && (
  <CredibilityCard summary={backtest.summary} onHoldout={onHoldout} holdoutRunning={holdoutRunning} />
)}
```

（import `CredibilityCard`；跟随该文件现有布局把卡片放在统计卡片区之前。）

- [ ] **Step 3: BacktestTool.tsx holdout 逻辑**

```tsx
  const [startingHoldout, setStartingHoldout] = useState(false)

  const runHoldout = async () => {
    if (!backtest?.run_id) return
    try {
      setStartingHoldout(true)
      const prevEnd = fromLocalInputValue(form.end_time)
      const windowMs = new Date(prevEnd).getTime() - new Date(fromLocalInputValue(form.start_time)).getTime()
      const start = new Date(new Date(prevEnd).getTime())
      const end = new Date(Math.min(Date.now() - 10 * 60 * 1000, start.getTime() + windowMs))
      if (end.getTime() <= start.getTime()) {
        throw new Error(t('backtestTool.holdoutNoData', 'No unseen time window after the tested range yet'))
      }
      const task = await createEventContractHoldoutTask(backtest.run_id, {
        start_time: start.toISOString(),
        end_time: end.toISOString(),
      })
      window.localStorage.setItem(BACKTEST_TASK_STORAGE_KEY, String(task.task_id))
      setTaskStatus(task)
      toast.success(t('backtestTool.holdoutStarted', 'Frozen-parameter verification started on a new window'))
    } catch (error: any) {
      toast.error(error?.message || t('backtestTool.holdoutFailed', 'Holdout run failed'))
    } finally {
      setStartingHoldout(false)
    }
  }
```

（import `createEventContractHoldoutTask`；`EventBacktestResponse` 需含 `run_id`——已有。）向 `BacktestResultsPanel` 传 `onHoldout={runHoldout}` 和 `holdoutRunning={startingHoldout}`。

- [ ] **Step 4: i18n（EN + ZH 同加）**

`en.json`：

```json
"credibility": "Credibility",
"holdoutRun": "Verify on new window",
"sampleSize": "{{count}} decided trades",
"winRateCi": "Win rate 95% CI: {{low}}%–{{high}}%",
"significant": "Beats breakeven {{be}}% (p={{p}})",
"notSignificant": "Not proven above breakeven {{be}}%",
"insufficientSample": "Sample too small to judge",
"sensitivity": "Settlement sensitivity: {{b2}}% of results flip at ±2bps, {{b5}}% at ±5bps, {{b10}}% at ±10bps.",
"calibration": "Calibration (Brier {{score}}):",
"calibrationBucket": "Predicted {{range}}% → actual {{actual}}% (n={{n}})",
"holdoutStarted": "Frozen-parameter verification started on a new window",
"holdoutFailed": "Holdout run failed",
"holdoutNoData": "No unseen time window after the tested range yet"
```

`zh.json`：

```json
"credibility": "可信度",
"holdoutRun": "换新时段验证",
"sampleSize": "{{count}} 笔有效交易",
"winRateCi": "胜率 95% 置信区间：{{low}}%–{{high}}%",
"significant": "显著高于盈亏平衡线 {{be}}%（p={{p}}）",
"notSignificant": "尚不能证明高于盈亏平衡线 {{be}}%",
"insufficientSample": "样本太小，无法下结论",
"sensitivity": "结算敏感度：±2bps 时 {{b2}}% 的结果会翻转，±5bps 时 {{b5}}%，±10bps 时 {{b10}}%。",
"calibration": "概率校准（Brier {{score}}）：",
"calibrationBucket": "预测 {{range}}% → 实际 {{actual}}%（n={{n}}）",
"holdoutStarted": "已用冻结参数在新时段启动验证",
"holdoutFailed": "验证启动失败",
"holdoutNoData": "测试区间之后暂无未见过的数据时段"
```

- [ ] **Step 5: 构建验证**

Run: `pnpm build:frontend`
Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add frontend/app/components/backtest/CredibilityCard.tsx frontend/app/components/backtest/BacktestResultsPanel.tsx frontend/app/components/backtest/BacktestTool.tsx frontend/app/locales/en.json frontend/app/locales/zh.json
git commit -m "Add credibility card with CI/significance/sensitivity and holdout button"
```

---

### Task 13: 静态守护测试 + 全量验证

**Files:**
- Create: `backend/tests/test_backtest_tool_credibility_static.py`
- Test: 全量回归

**Interfaces:**
- Consumes: Task 11/12 的前端源码不变量。

- [ ] **Step 1: 写静态测试（拆分感知模式：拼接 backtest/ 下所有 tsx）**

```python
# backend/tests/test_backtest_tool_credibility_static.py
"""Static guards: platform presets + credibility card stay wired into the UI."""
from pathlib import Path

FRONTEND_BACKTEST = Path(__file__).resolve().parents[2] / "frontend" / "app" / "components" / "backtest"


def _source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(FRONTEND_BACKTEST.rglob("*.ts*")))


def test_platform_selector_present():
    src = _source()
    assert "binance_event" in src
    assert "PLATFORM_FORM_PRESETS" in src


def test_credibility_card_wired():
    src = _source()
    assert "CredibilityCard" in src
    assert "win_rate_ci_low" in src
    assert "createEventContractHoldoutTask" in src


def test_non_overlapping_toggle_present():
    assert "non_overlapping_only" in _source()
```

- [ ] **Step 2: 全量回归**

Run: `cd backend && uv run pytest -q`
Expected: 全部通过
Run: `pnpm build:frontend`
Expected: 构建成功

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_backtest_tool_credibility_static.py
git commit -m "Add static guards for backtest tool credibility UI"
```

---

## Self-Review 结果

- **Spec 覆盖**：P0.1→Task 1；P0.2→Task 3（含 delay 默认 3 在 Task 2）；P0.3 滑点语义→Task 3 说明 + 路由描述不改行为（保留现有 `_apply_slippage`，其"基准价不利漂移"语义在 spec 中已确认为正确模型）；P0.4→Task 2、4；P1.1→Task 5；P1.2→Task 7（sensitivity）；P1.3→Task 6；P2.1→Task 7；P2.2→Task 8；P2.3→Task 9；P2.4→Task 10；P3→Task 11、12；测试→各 Task + Task 13。
- **占位符**：无 TBD/TODO；所有步骤含完整代码。
- **类型一致性**：`_resolve_entry_bar` 签名在 Task 3 定义并仅在 Task 3 使用；`TradeConstraintTracker` 键名与 `skipped` 计数键一致；前端 `EventBacktestSummary` 字段与 Task 7/9/10 后端键一一对应；`_load_reviewer_weights(db, cfg)` 两处调用点均已列出。
