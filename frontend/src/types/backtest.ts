import { ConditionRule } from '../stores/strategy'

export interface BacktestRequest {
  symbol: string
  exchange_a: string
  exchange_b: string
  start_time: string
  end_time: string
  conditions: ConditionRule[]
  initial_balance: number
  trade_fraction: number
  maker_fee_rate: number
  taker_fee_rate: number
  cooldown_seconds: number
  min_trade_amount: number
  slippage_model: 'simple' | 'orderbook'
  slippage_multiplier: number
}

export interface EquityPoint {
  timestamp: string
  balance: number
  pnl: number
}

export interface TradeRecord {
  timestamp: string
  spread_pct: number
  trade_amount: number
  slippage_pct: number
  fees: number
  pnl: number
  balance_after: number
  direction: string
}

export interface BacktestResult {
  equity_curve: EquityPoint[]
  trades: TradeRecord[]
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  max_drawdown: number
  sharpe_ratio: number
  final_balance: number
  execution_time_ms: number
}

export interface AvailableRange {
  symbol: string
  exchange_a: string
  exchange_b: string
  start_time: string
  end_time: string
}
