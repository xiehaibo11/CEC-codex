import logging
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from sqlalchemy.orm import Session
from database.models import Position
from .market_data import get_last_price

logger = logging.getLogger(__name__)

# Positions typically number in the single digits per account; this just
# needs to be large enough that a cold-cache request fetches prices
# concurrently instead of serially, one blocking exchange call at a time.
_PRICE_FETCH_MAX_WORKERS = 10


def _fetch_position_value(position: Position) -> Decimal:
    try:
        price = Decimal(str(get_last_price(position.symbol, position.market)))
        return price * Decimal(position.quantity)
    except Exception as e:
        # Log error but don't interrupt calculation, skip position if price cannot be obtained
        logger.warning(
            f"Cannot get price for {position.symbol}.{position.market}, "
            f"skipping position value calculation: {e}"
        )
        return Decimal("0")


def calc_positions_value(db: Session, account_id: int) -> float:
    """
    Calculate total market value of positions

    Args:
        db: Database session
        account_id: Account ID

    Returns:
        Total market value of positions, returns 0 if price cannot be obtained
    """
    positions = db.query(Position).filter(Position.account_id == account_id).all()
    if not positions:
        return 0.0

    # Fetch prices concurrently (each is a blocking cache/exchange call) so a
    # cold cache doesn't serialize N sequential network round-trips.
    with ThreadPoolExecutor(max_workers=min(_PRICE_FETCH_MAX_WORKERS, len(positions))) as executor:
        values = list(executor.map(_fetch_position_value, positions))

    total = sum(values, Decimal("0"))
    return float(total)
