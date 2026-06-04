import { Router } from "express";
import { GetCoinParams, ListCoinsQueryParams } from "@workspace/api-zod";
import {
  getMarkets,
  getMarketsWithSparkline,
  type CoinGeckoMarket,
} from "../lib/coinGeckoCache";
import { computeTA, type TAResult } from "../lib/technicalAnalysis";
import { getFundingRate } from "../lib/fundingRates";

const router = Router();

export interface CoinSignal {
  id: string;
  symbol: string;
  name: string;
  image: string;
  current_price: number;
  market_cap: number;
  market_cap_rank: number;
  price_change_percentage_24h: number | null;
  price_change_percentage_7d_in_currency: number | null;
  total_volume: number;
  ath: number | null;
  ath_change_percentage: number | null;
  signal: "buy_long" | "sell_short" | "neutral";
  signal_strength: number;
  signal_reasons: string[];
  ta?: TAResult;
  funding_rate?: number | null;
}

// ─── Core signal logic (sync, accepts optional pre-computed TA & funding rate)

export function computeSignal(
  coin: CoinGeckoMarket,
  ta?: TAResult | null,
  fundingRate?: number | null
): {
  signal: "buy_long" | "sell_short" | "neutral";
  signal_strength: number;
  signal_reasons: string[];
} {
  let score = 0;
  const reasons: string[] = [];

  const change24h = coin.price_change_percentage_24h ?? 0;
  const change7d = coin.price_change_percentage_7d_in_currency ?? 0;
  const athChange = coin.ath_change_percentage ?? 0;
  const volumeToMarketCap =
    coin.market_cap > 0 ? coin.total_volume / coin.market_cap : 0;

  // ── 24h momentum ────────────────────────────────────────────────────────────
  if (change24h > 5) {
    score += 20;
    reasons.push(`Strong 24h gain: +${change24h.toFixed(1)}%`);
  } else if (change24h > 2) {
    score += 10;
    reasons.push(`Positive 24h momentum: +${change24h.toFixed(1)}%`);
  } else if (change24h < -5) {
    score -= 20;
    reasons.push(`Sharp 24h decline: ${change24h.toFixed(1)}%`);
  } else if (change24h < -2) {
    score -= 10;
    reasons.push(`Negative 24h pressure: ${change24h.toFixed(1)}%`);
  }

  // ── 7d trend ────────────────────────────────────────────────────────────────
  if (change7d > 10) {
    score += 20;
    reasons.push(`Strong 7d uptrend: +${change7d.toFixed(1)}%`);
  } else if (change7d > 3) {
    score += 10;
    reasons.push(`7d upward momentum: +${change7d.toFixed(1)}%`);
  } else if (change7d < -10) {
    score -= 20;
    reasons.push(`7d downtrend confirmed: ${change7d.toFixed(1)}%`);
  } else if (change7d < -3) {
    score -= 10;
    reasons.push(`7d bearish trend: ${change7d.toFixed(1)}%`);
  }

  // ── Volume spike ─────────────────────────────────────────────────────────────
  if (volumeToMarketCap > 0.15) {
    const direction = change24h >= 0 ? "bullish" : "bearish";
    score += change24h >= 0 ? 15 : -15;
    reasons.push(
      `High volume spike (${(volumeToMarketCap * 100).toFixed(0)}% of mkt cap) — ${direction}`
    );
  } else if (volumeToMarketCap > 0.08) {
    score += change24h >= 0 ? 7 : -7;
    reasons.push(`Elevated volume activity`);
  }

  // ── ATH distance ─────────────────────────────────────────────────────────────
  if (athChange > -5) {
    score -= 10;
    reasons.push(`Near all-time high — potential resistance`);
  } else if (athChange < -80) {
    score += 12;
    reasons.push(`Deep ATH discount (${athChange.toFixed(0)}%) — oversold territory`);
  } else if (athChange < -50) {
    score += 6;
    reasons.push(`Significant ATH discount: ${athChange.toFixed(0)}%`);
  }

  // ── RSI ──────────────────────────────────────────────────────────────────────
  if (ta?.rsi != null) {
    const rsi = ta.rsi;
    if (rsi < 25) {
      score += 25;
      reasons.push(`RSI ${rsi} — extremely oversold (strong buy zone)`);
    } else if (rsi < 35) {
      score += 15;
      reasons.push(`RSI ${rsi} — oversold (buy signal)`);
    } else if (rsi < 45) {
      score += 5;
      reasons.push(`RSI ${rsi} — leaning oversold`);
    } else if (rsi > 75) {
      score -= 25;
      reasons.push(`RSI ${rsi} — extremely overbought (strong sell zone)`);
    } else if (rsi > 65) {
      score -= 15;
      reasons.push(`RSI ${rsi} — overbought (sell signal)`);
    } else if (rsi > 55) {
      score -= 5;
      reasons.push(`RSI ${rsi} — leaning overbought`);
    } else {
      reasons.push(`RSI ${rsi} — neutral zone`);
    }
  }

  // ── MACD ─────────────────────────────────────────────────────────────────────
  if (ta?.macd != null) {
    const { histogram } = ta.macd;
    if (histogram > 0) {
      score += 15;
      reasons.push(`MACD histogram positive — bullish momentum`);
    } else if (histogram < 0) {
      score -= 15;
      reasons.push(`MACD histogram negative — bearish momentum`);
    }
  }

  // ── Bollinger Bands ───────────────────────────────────────────────────────────
  if (ta?.bb != null) {
    const { pctB } = ta.bb;
    if (pctB < 0.1) {
      score += 20;
      reasons.push(`Price below BB lower band (%B ${(pctB * 100).toFixed(0)}%) — strong buy zone`);
    } else if (pctB < 0.25) {
      score += 10;
      reasons.push(`Price near BB lower band (%B ${(pctB * 100).toFixed(0)}%) — buy zone`);
    } else if (pctB > 0.9) {
      score -= 20;
      reasons.push(`Price above BB upper band (%B ${(pctB * 100).toFixed(0)}%) — strong sell zone`);
    } else if (pctB > 0.75) {
      score -= 10;
      reasons.push(`Price near BB upper band (%B ${(pctB * 100).toFixed(0)}%) — sell zone`);
    }
  }

  // ── Funding Rate (contrarian) ─────────────────────────────────────────────────
  if (fundingRate != null) {
    const pct = fundingRate * 100;
    if (fundingRate > 0.001) {
      score -= 20;
      reasons.push(`Funding rate +${pct.toFixed(4)}% — longs paying shorts (bearish sentiment)`);
    } else if (fundingRate > 0.0005) {
      score -= 10;
      reasons.push(`Funding rate +${pct.toFixed(4)}% — elevated longs (mildly bearish)`);
    } else if (fundingRate < -0.001) {
      score += 20;
      reasons.push(`Funding rate ${pct.toFixed(4)}% — shorts paying longs (bullish sentiment)`);
    } else if (fundingRate < -0.0005) {
      score += 10;
      reasons.push(`Funding rate ${pct.toFixed(4)}% — elevated shorts (mildly bullish)`);
    } else {
      reasons.push(`Funding rate ${pct.toFixed(4)}% — neutral`);
    }
  }

  const clamped = Math.max(-100, Math.min(100, score));
  let signal: "buy_long" | "sell_short" | "neutral";
  if (clamped >= 20) signal = "buy_long";
  else if (clamped <= -20) signal = "sell_short";
  else signal = "neutral";

  if (reasons.length === 0) {
    reasons.push("No strong directional signals detected");
  }

  return { signal, signal_strength: clamped, signal_reasons: reasons };
}

// ─── Async full signal (fetches sparkline TA + funding rate) ─────────────────

export async function computeSignalFull(coin: CoinGeckoMarket): Promise<{
  signal: "buy_long" | "sell_short" | "neutral";
  signal_strength: number;
  signal_reasons: string[];
  ta: TAResult | null;
  funding_rate: number | null;
}> {
  const prices = coin.sparkline_in_7d?.price ?? [];
  const ta = prices.length >= 27 ? computeTA(prices) : null;
  const funding_rate = await getFundingRate(coin.id, coin.symbol);
  const result = computeSignal(coin, ta, funding_rate);
  return { ...result, ta, funding_rate };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function toCoinSignal(coin: CoinGeckoMarket): CoinSignal {
  const { signal, signal_strength, signal_reasons } = computeSignal(coin);
  return {
    id: coin.id,
    symbol: coin.symbol,
    name: coin.name,
    image: coin.image,
    current_price: coin.current_price,
    market_cap: coin.market_cap,
    market_cap_rank: coin.market_cap_rank,
    price_change_percentage_24h: coin.price_change_percentage_24h,
    price_change_percentage_7d_in_currency: coin.price_change_percentage_7d_in_currency,
    total_volume: coin.total_volume,
    ath: coin.ath,
    ath_change_percentage: coin.ath_change_percentage,
    signal,
    signal_strength,
    signal_reasons,
  };
}

// ─── Routes ──────────────────────────────────────────────────────────────────

router.get("/coins", async (req, res) => {
  const parsed = ListCoinsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query params" });
    return;
  }

  const { per_page = 50, signal: signalFilter } = parsed.data;

  try {
    const markets = await getMarkets(Math.min(per_page, 250));
    const coins = markets.map(toCoinSignal);
    const filtered = signalFilter ? coins.filter((c) => c.signal === signalFilter) : coins;
    res.json(filtered);
  } catch (err) {
    req.log.error({ err }, "Failed to fetch coins");
    res.status(502).json({ error: "Failed to fetch market data" });
  }
});

router.get("/coins/:id", async (req, res) => {
  const parsed = GetCoinParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid params" });
    return;
  }

  const { id } = parsed.data;

  try {
    const markets = await getMarketsWithSparkline();
    const coin = markets.find((c) => c.id === id);

    if (!coin) {
      res.status(404).json({ error: "Coin not found" });
      return;
    }

    const { signal, signal_strength, signal_reasons, ta, funding_rate } =
      await computeSignalFull(coin);

    res.json({
      id: coin.id,
      symbol: coin.symbol,
      name: coin.name,
      image: coin.image,
      current_price: coin.current_price,
      market_cap: coin.market_cap,
      market_cap_rank: coin.market_cap_rank,
      price_change_percentage_24h: coin.price_change_percentage_24h,
      price_change_percentage_7d_in_currency: coin.price_change_percentage_7d_in_currency,
      price_change_percentage_30d_in_currency: coin.price_change_percentage_30d_in_currency,
      total_volume: coin.total_volume,
      ath: coin.ath,
      ath_change_percentage: coin.ath_change_percentage,
      circulating_supply: coin.circulating_supply,
      total_supply: coin.total_supply,
      signal,
      signal_strength,
      signal_reasons,
      sparkline_in_7d: coin.sparkline_in_7d?.price ?? [],
      ta,
      funding_rate,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to fetch coin detail");
    res.status(502).json({ error: "Failed to fetch coin data" });
  }
});

router.get("/signals", async (req, res) => {
  try {
    const markets = await getMarkets(100);

    const groups: {
      buy_long: CoinSignal[];
      sell_short: CoinSignal[];
      neutral: CoinSignal[];
    } = { buy_long: [], sell_short: [], neutral: [] };

    for (const coin of markets) {
      const entry = toCoinSignal(coin);
      groups[entry.signal].push(entry);
    }

    res.json(groups);
  } catch (err) {
    req.log.error({ err }, "Failed to fetch signals");
    res.status(502).json({ error: "Failed to fetch signal data" });
  }
});

export default router;
