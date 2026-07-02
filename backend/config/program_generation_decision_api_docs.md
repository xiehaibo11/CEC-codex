
## Decision Object (return from should_trade)

Your should_trade method must return a Decision object:

```python
# For BUY (open long position):
return Decision(
    operation="buy",                    # Required: "buy", "sell", "close", "hold"
    symbol="BTC",                       # Required: Trading symbol
    target_portion_of_balance=0.5,      # Required: 0.1-1.0 (portion of balance to use)
    leverage=10,                        # Required: 1-50
    max_price=95000.0,                  # Required for buy: maximum entry price
    time_in_force="Ioc",                # Optional: "Ioc", "Gtc", "Alo" (default: "Ioc")
    take_profit_price=100000.0,         # Optional: TP trigger price
    stop_loss_price=90000.0,            # Optional: SL trigger price
    tp_execution="limit",               # Optional: "market" or "limit" (default: "limit")
    sl_execution="limit",               # Optional: "market" or "limit" (default: "limit")
    reason="RSI oversold",              # Optional: Reason for decision
    trading_strategy="Entry thesis..."  # Optional: Strategy description
)

# For SELL (open short position):
return Decision(
    operation="sell",
    symbol="BTC",
    target_portion_of_balance=0.5,
    leverage=10,
    min_price=95000.0,                  # Required for sell: minimum entry price
    ...
)

# For CLOSE (close existing position):
return Decision(
    operation="close",
    symbol="BTC",
    target_portion_of_balance=1.0,      # Portion of position to close
    leverage=10,
    min_price=95000.0,                  # Required for closing LONG position
    # OR max_price=95000.0,             # Required for closing SHORT position
    ...
)

# For HOLD (no action):
return Decision(operation="hold", symbol="BTC", reason="No trade condition")
```

### Operation Types
- "buy" - Open long position (requires max_price)
- "sell" - Open short position (requires min_price)
- "close" - Close existing position (requires min_price for long, max_price for short)
- "hold" - No action

### Decision Fields
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| operation | str | Yes | - | "buy", "sell", "close", "hold" |
| symbol | str | Yes | - | Trading symbol (e.g., "BTC") |
| target_portion_of_balance | float | For buy/sell/close | 0.0 | 0.1-1.0 |
| leverage | int | For buy/sell/close | 10 | 1-50 |
| max_price | float | For buy/close short | None | Maximum entry price |
| min_price | float | For sell/close long | None | Minimum entry price |
| time_in_force | str | No | "Ioc" | "Ioc", "Gtc", "Alo" |
| take_profit_price | float | No | None | TP trigger price |
| stop_loss_price | float | No | None | SL trigger price |
| tp_execution | str | No | "limit" | "market" or "limit" |
| sl_execution | str | No | "limit" | "market" or "limit" |
| reason | str | No | "" | Reason for decision |
| trading_strategy | str | No | "" | Entry thesis, risk controls |

### Time In Force Options
- "Ioc" (Immediate or Cancel): Fill immediately or cancel unfilled portion
- "Gtc" (Good Till Cancel): Order stays in orderbook until filled or cancelled
- "Alo" (Add Liquidity Only): Maker-only order, rejected if would take liquidity
