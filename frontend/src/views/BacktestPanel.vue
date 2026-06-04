<template>
  <div class="p-4 max-w-7xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-xl font-bold text-white">回测面板</h2>
      <span v-if="result" class="text-sm text-gray-400">
        执行耗时: <span class="text-green-400">{{ result.execution_time_ms.toFixed(0) }}ms</span>
      </span>
    </div>

    <!-- Parameters Form -->
    <div class="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
      <h3 class="text-sm font-medium text-gray-300 mb-3">回测参数</h3>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div>
          <label class="block text-xs text-gray-500 mb-1">交易对</label>
          <select v-model="form.symbol" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
            <option value="BTC/USDT">BTC/USDT</option>
            <option value="ETH/USDT">ETH/USDT</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">交易所 A</label>
          <select v-model="form.exchange_a" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
            <option value="binance">Binance</option>
            <option value="okx">OKX</option>
            <option value="huobi">Huobi</option>
            <option value="mock_binance">Mock Binance</option>
            <option value="mock_okx">Mock OKX</option>
            <option value="mock_huobi">Mock Huobi</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">交易所 B</label>
          <select v-model="form.exchange_b" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
            <option value="binance">Binance</option>
            <option value="okx">OKX</option>
            <option value="huobi">Huobi</option>
            <option value="mock_binance">Mock Binance</option>
            <option value="mock_okx">Mock OKX</option>
            <option value="mock_huobi">Mock Huobi</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">初始资金 (USDT)</label>
          <input v-model.number="form.initial_balance" type="number" min="100"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div>
          <label class="block text-xs text-gray-500 mb-1">开始时间</label>
          <input v-model="form.start_time" type="datetime-local"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">结束时间</label>
          <input v-model="form.end_time" type="datetime-local"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">下单比例</label>
          <input v-model.number="form.trade_fraction" type="number" step="0.01" min="0.01" max="1"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">冷却时间 (秒)</label>
          <input v-model.number="form.cooldown_seconds" type="number" min="0"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div>
          <label class="block text-xs text-gray-500 mb-1">Maker 手续费</label>
          <input v-model.number="form.maker_fee_rate" type="number" step="0.0001" min="0"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Taker 手续费</label>
          <input v-model.number="form.taker_fee_rate" type="number" step="0.0001" min="0"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">滑点模型</label>
          <select v-model="form.slippage_model" class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
            <option value="simple">简单模型</option>
            <option value="orderbook">订单簿深度</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">滑点系数</label>
          <input v-model.number="form.slippage_multiplier" type="number" step="0.0001" min="0"
            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
        </div>
      </div>

      <!-- Conditions Builder -->
      <div class="mb-4">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-xs text-gray-500">触发条件</span>
          <button @click="addCondition" class="px-2 py-0.5 text-xs rounded bg-blue-600 text-white hover:bg-blue-500">
            + 添加
          </button>
        </div>
        <div v-if="form.conditions.length" class="space-y-2">
          <div v-for="(cond, idx) in form.conditions" :key="idx"
            class="flex items-center gap-2 bg-gray-900 rounded px-3 py-2">
            <select v-model="cond.field" class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white">
              <option value="spread_pct">价差 %</option>
              <option value="best_spread">最佳价差</option>
              <option value="volume">交易量</option>
            </select>
            <select v-model="cond.operator" class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white">
              <option value=">">&gt;</option>
              <option value=">=">&gt;=</option>
              <option value="<">&lt;</option>
              <option value="<=">&lt;=</option>
              <option value="==">==</option>
            </select>
            <input v-model.number="cond.value" type="number" step="0.01"
              class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white w-24" />
            <button @click="form.conditions.splice(idx, 1)" class="text-red-400 hover:text-red-300 text-xs">删除</button>
          </div>
        </div>
      </div>

      <button @click="startBacktest" :disabled="!canSubmit || loading"
        class="px-6 py-2 rounded bg-green-600 text-white font-medium hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed">
        {{ loading ? '回测中...' : '开始回测' }}
      </button>

      <span v-if="error" class="ml-4 text-sm text-red-400">{{ error }}</span>
    </div>

    <!-- Results -->
    <div v-if="result" class="space-y-4">
      <!-- Metrics Cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div class="text-xs text-gray-500">总盈亏</div>
          <div :class="result.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'" class="text-lg font-bold">
            {{ result.total_pnl >= 0 ? '+' : '' }}{{ result.total_pnl.toFixed(2) }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div class="text-xs text-gray-500">胜率</div>
          <div class="text-lg font-bold text-white">{{ (result.win_rate * 100).toFixed(1) }}%</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div class="text-xs text-gray-500">最大回撤</div>
          <div class="text-lg font-bold text-red-400">{{ (result.max_drawdown * 100).toFixed(2) }}%</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div class="text-xs text-gray-500">夏普比率</div>
          <div class="text-lg font-bold text-white">{{ result.sharpe_ratio.toFixed(2) }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div class="text-xs text-gray-500">总交易</div>
          <div class="text-lg font-bold text-white">{{ result.total_trades }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div class="text-xs text-gray-500">最终余额</div>
          <div class="text-lg font-bold text-white">{{ result.final_balance.toFixed(2) }}</div>
        </div>
      </div>

      <!-- Equity Curve Chart -->
      <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 class="text-sm font-medium text-gray-300 mb-3">收益曲线</h3>
        <div ref="chartContainer" class="h-64"></div>
      </div>

      <!-- Trade Table -->
      <div class="bg-gray-800 rounded-lg border border-gray-700">
        <div class="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-300">交易记录 ({{ result.trades.length }})</h3>
          <button @click="showAllTrades = !showAllTrades" class="text-xs text-gray-500 hover:text-white">
            {{ showAllTrades ? '收起' : '展开全部' }}
          </button>
        </div>
        <div class="overflow-x-auto max-h-64 overflow-y-auto">
          <table class="w-full text-xs text-gray-300">
            <thead class="text-gray-500 sticky top-0 bg-gray-800">
              <tr>
                <th class="px-3 py-2 text-left">时间</th>
                <th class="px-3 py-2 text-right">价差%</th>
                <th class="px-3 py-2 text-right">下单量</th>
                <th class="px-3 py-2 text-right">手续费</th>
                <th class="px-3 py-2 text-right">盈亏</th>
                <th class="px-3 py-2 text-right">余额</th>
                <th class="px-3 py-2 text-left">方向</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(trade, idx) in displayedTrades" :key="idx"
                class="border-t border-gray-700 hover:bg-gray-750">
                <td class="px-3 py-1.5">{{ formatTime(trade.timestamp) }}</td>
                <td class="px-3 py-1.5 text-right">{{ trade.spread_pct.toFixed(4) }}</td>
                <td class="px-3 py-1.5 text-right">{{ trade.trade_amount.toFixed(2) }}</td>
                <td class="px-3 py-1.5 text-right text-yellow-400">{{ trade.fees.toFixed(4) }}</td>
                <td class="px-3 py-1.5 text-right" :class="trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ trade.pnl >= 0 ? '+' : '' }}{{ trade.pnl.toFixed(4) }}
                </td>
                <td class="px-3 py-1.5 text-right">{{ trade.balance_after.toFixed(2) }}</td>
                <td class="px-3 py-1.5">{{ trade.direction }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useBacktestStore } from '../stores/backtest'
import { createChart, type IChartApi, type ISeriesApi, ColorType } from 'lightweight-charts'
import type { ConditionRule } from '../stores/strategy'

const store = useBacktestStore()

const chartContainer = ref<HTMLElement | null>(null)
const showAllTrades = ref(false)

let chart: IChartApi | null = null
let series: ISeriesApi<'Area'> | null = null

const result = computed(() => store.result)
const loading = computed(() => store.loading)
const error = computed(() => store.error)

const form = ref({
  symbol: 'BTC/USDT',
  exchange_a: 'mock_binance',
  exchange_b: 'mock_okx',
  start_time: getDefaultStartTime(),
  end_time: getDefaultEndTime(),
  initial_balance: 10000,
  trade_fraction: 0.10,
  cooldown_seconds: 5,
  maker_fee_rate: 0.001,
  taker_fee_rate: 0.001,
  min_trade_amount: 1.0,
  slippage_model: 'simple' as const,
  slippage_multiplier: 0.0005,
  conditions: [] as ConditionRule[],
})

const canSubmit = computed(() =>
  form.value.conditions.length > 0 &&
  form.value.start_time &&
  form.value.end_time &&
  form.value.initial_balance >= 100
)

const displayedTrades = computed(() => {
  if (!result.value) return []
  return showAllTrades.value ? result.value.trades : result.value.trades.slice(0, 20)
})

function getDefaultStartTime(): string {
  const d = new Date()
  d.setDate(d.getDate() - 7)
  return d.toISOString().slice(0, 16)
}

function getDefaultEndTime(): string {
  return new Date().toISOString().slice(0, 16)
}

function addCondition() {
  form.value.conditions.push({ field: 'spread_pct', operator: '>', value: 0.1 })
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

async function startBacktest() {
  const request = {
    ...form.value,
    start_time: new Date(form.value.start_time).toISOString(),
    end_time: new Date(form.value.end_time).toISOString(),
  }
  await store.runBacktest(request)
}

function renderChart() {
  if (!result.value || !chartContainer.value) return

  if (chart) {
    chart.remove()
    chart = null
  }

  chart = createChart(chartContainer.value, {
    layout: {
      background: { type: ColorType.Solid, color: '#1f2937' },
      textColor: '#9ca3af',
    },
    grid: {
      vertLines: { color: '#374151' },
      horzLines: { color: '#374151' },
    },
    width: chartContainer.value.clientWidth,
    height: 256,
    timeScale: { timeVisible: true },
  })

  series = chart.addAreaSeries({
    lineColor: '#10b981',
    topColor: 'rgba(16, 185, 129, 0.3)',
    bottomColor: 'rgba(16, 185, 129, 0.0)',
    lineWidth: 2,
  })

  const data = result.value.equity_curve.map(p => ({
    time: Math.floor(new Date(p.timestamp).getTime() / 1000) as any,
    value: p.balance,
  }))

  if (data.length > 0) {
    series.setData(data)
    chart.timeScale().fitContent()
  }
}

watch(result, async (val) => {
  if (val) {
    await nextTick()
    renderChart()
  }
})

onMounted(() => {
  store.fetchAvailableRanges()
})
</script>
