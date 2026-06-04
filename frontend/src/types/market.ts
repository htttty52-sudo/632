export interface OrderBookLevel {
  price: number
  quantity: number
}

export interface UnifiedOrderBook {
  msg_id: string
  exchange: string
  symbol: string
  timestamp: number
  sequence: number
  bids: OrderBookLevel[]
  asks: OrderBookLevel[]
}

export interface UnifiedTrade {
  msg_id: string
  exchange: string
  symbol: string
  trade_id: string
  price: number
  quantity: number
  side: 'buy' | 'sell'
  timestamp: number
}

export interface SpreadSnapshot {
  symbol: string
  exchange_a: string
  exchange_b: string
  a_best_bid: number
  a_best_ask: number
  b_best_bid: number
  b_best_ask: number
  spread: number
  spread_pct: number
  timestamp: number
}

export interface SpreadCell {
  exchange_a: string
  exchange_b: string
  spread_ab: number
  spread_ba: number
  best_spread: number
  spread_pct: number
}

export interface SpreadMatrix {
  symbol: string
  exchanges: string[]
  cells: SpreadCell[]
  stale_exchanges: string[]
  timestamp: number
}

export interface SpreadAlertEvent {
  symbol: string
  exchange_a: string
  exchange_b: string
  spread_pct: number
  direction: string
  timestamp: number
}

export interface WSMessage {
  type: 'orderbook' | 'trade' | 'spread' | 'spread_matrix' | 'spread_alert'
  data: UnifiedOrderBook | UnifiedTrade | SpreadSnapshot | SpreadMatrix | SpreadAlertEvent
}
