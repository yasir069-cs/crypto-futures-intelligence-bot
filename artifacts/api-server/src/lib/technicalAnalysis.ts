export interface TAResult {
  rsi: number | null;
  macd: { macd: number; signal: number; histogram: number } | null;
  bb: { upper: number; middle: number; lower: number; pctB: number } | null;
}

// ─── EMA ────────────────────────────────────────────────────────────────────

function ema(prices: number[], period: number): number[] {
  if (prices.length < period) return [];
  const k = 2 / (period + 1);
  const result: number[] = [];
  let prev = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result.push(prev);
  for (let i = period; i < prices.length; i++) {
    prev = prices[i] * k + prev * (1 - k);
    result.push(prev);
  }
  return result;
}

// ─── RSI (Wilder smoothing, 14-period) ──────────────────────────────────────

export function computeRSI(prices: number[], period = 14): number | null {
  if (prices.length < period + 1) return null;

  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = prices[i] - prices[i - 1];
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < prices.length; i++) {
    const diff = prices[i] - prices[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
  }

  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return Math.round((100 - 100 / (1 + rs)) * 10) / 10;
}

// ─── MACD (12, 26, 9) ───────────────────────────────────────────────────────

export function computeMACD(
  prices: number[],
  fast = 12,
  slow = 26,
  signal = 9
): { macd: number; signal: number; histogram: number } | null {
  if (prices.length < slow + signal) return null;

  const fastEMA = ema(prices, fast);
  const slowEMA = ema(prices, slow);

  const offset = fast - 1;
  const macdLine: number[] = [];
  for (let i = 0; i < slowEMA.length; i++) {
    macdLine.push(fastEMA[i + offset] - slowEMA[i]);
  }

  if (macdLine.length < signal) return null;

  const signalLine = ema(macdLine, signal);
  const lastMACD = macdLine[macdLine.length - 1];
  const lastSignal = signalLine[signalLine.length - 1];
  const histogram = lastMACD - lastSignal;

  return {
    macd: Math.round(lastMACD * 1e8) / 1e8,
    signal: Math.round(lastSignal * 1e8) / 1e8,
    histogram: Math.round(histogram * 1e8) / 1e8,
  };
}

// ─── Bollinger Bands (20-period, 2 stddev) ───────────────────────────────────

export function computeBB(
  prices: number[],
  period = 20,
  stdDevMultiplier = 2
): { upper: number; middle: number; lower: number; pctB: number } | null {
  if (prices.length < period) return null;

  const recent = prices.slice(-period);
  const sma = recent.reduce((a, b) => a + b, 0) / period;
  const variance = recent.reduce((sum, p) => sum + (p - sma) ** 2, 0) / period;
  const stdDev = Math.sqrt(variance);

  const upper = sma + stdDevMultiplier * stdDev;
  const lower = sma - stdDevMultiplier * stdDev;
  const lastPrice = prices[prices.length - 1];
  const pctB = stdDev === 0 ? 0.5 : (lastPrice - lower) / (upper - lower);

  return {
    upper: Math.round(upper * 1e8) / 1e8,
    middle: Math.round(sma * 1e8) / 1e8,
    lower: Math.round(lower * 1e8) / 1e8,
    pctB: Math.round(pctB * 1000) / 1000,
  };
}

// ─── Combined TA ─────────────────────────────────────────────────────────────

export function computeTA(prices: number[]): TAResult {
  return {
    rsi: computeRSI(prices),
    macd: computeMACD(prices),
    bb: computeBB(prices),
  };
}
