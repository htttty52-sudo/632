from dataclasses import dataclass


@dataclass
class FeeConfig:
    maker_fee_rate: float = 0.001
    taker_fee_rate: float = 0.001

    @property
    def round_trip_rate(self) -> float:
        return self.maker_fee_rate + self.taker_fee_rate


@dataclass
class SlippageResult:
    average_fill_price: float
    total_cost: float
    slippage_pct: float


OPERATOR_MAP = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
}


def evaluate_conditions(conditions: list[dict], ctx: dict) -> bool:
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "")
        threshold = cond.get("value", 0)
        if field not in ctx:
            return False
        op_fn = OPERATOR_MAP.get(operator)
        if not op_fn:
            return False
        if not op_fn(ctx[field], threshold):
            return False
    return True


def compute_trade_amount(balance: float, fraction: float = 0.10) -> float:
    return balance * fraction


def validate_trade(amount: float, min_amount: float = 1.0) -> bool:
    return amount >= min_amount


def compute_slippage_from_book(
    order_book_levels: list[tuple[float, float]],
    trade_size: float,
) -> SlippageResult:
    """Walk order book levels to compute average fill price for a given trade size."""
    if not order_book_levels or trade_size <= 0:
        return SlippageResult(average_fill_price=0.0, total_cost=0.0, slippage_pct=0.0)

    remaining = trade_size
    total_cost = 0.0
    best_price = order_book_levels[0][0]

    for price, qty in order_book_levels:
        fill_qty = min(remaining, qty)
        total_cost += fill_qty * price
        remaining -= fill_qty
        if remaining <= 0:
            break

    filled_qty = trade_size - max(remaining, 0)
    if filled_qty <= 0:
        return SlippageResult(average_fill_price=best_price, total_cost=0.0, slippage_pct=0.0)

    avg_price = total_cost / filled_qty
    slippage_pct = abs(avg_price - best_price) / best_price * 100 if best_price else 0.0

    return SlippageResult(
        average_fill_price=avg_price,
        total_cost=total_cost,
        slippage_pct=slippage_pct,
    )


def compute_slippage_simple(
    mid_price: float,
    trade_size: float,
    multiplier: float = 0.0005,
    base_unit: float = 1.0,
) -> SlippageResult:
    """Simple slippage model: linear function of trade size."""
    slippage_pct = multiplier * (trade_size / base_unit) * 100
    cost = mid_price * trade_size * multiplier
    avg_price = mid_price * (1 + multiplier * trade_size / base_unit)
    return SlippageResult(
        average_fill_price=avg_price,
        total_cost=cost,
        slippage_pct=slippage_pct,
    )


def compute_fees(trade_amount: float, fee_config: FeeConfig) -> float:
    return trade_amount * fee_config.round_trip_rate


def compute_pnl(
    spread_pct: float,
    trade_amount: float,
    fee_config: FeeConfig,
    slippage_pct: float = 0.0,
) -> float:
    gross_pnl = trade_amount * (spread_pct / 100.0)
    fees = compute_fees(trade_amount, fee_config)
    slippage_cost = trade_amount * (slippage_pct / 100.0)
    return gross_pnl - fees - slippage_cost
