import { logger } from "./logger";

const BINANCE_FUTURES_API = "https://fapi.binance.com/fapi/v1/premiumIndex";
const CACHE_TTL_MS = 5 * 60 * 1000;

interface BinancePremiumIndex {
  symbol: string;
  markPrice: string;
  lastFundingRate: string;
  nextFundingTime: number;
  time: number;
}

interface FundingCache {
  data: Map<string, number>;
  expiresAt: number;
}

let cache: FundingCache | null = null;
let flight: Promise<Map<string, number>> | null = null;

// Map CoinGecko IDs / symbols → Binance perpetual symbol roots
const SYMBOL_MAP: Record<string, string> = {
  bitcoin: "BTC",
  ethereum: "ETH",
  binancecoin: "BNB",
  solana: "SOL",
  ripple: "XRP",
  cardano: "ADA",
  dogecoin: "DOGE",
  avalanche: "AVAX",
  chainlink: "LINK",
  polkadot: "DOT",
  "shiba-inu": "SHIB",
  "matic-network": "MATIC",
  "wrapped-bitcoin": "WBTC",
  litecoin: "LTC",
  "bitcoin-cash": "BCH",
  "uniswap": "UNI",
  "the-sandbox": "SAND",
  "decentraland": "MANA",
  "axie-infinity": "AXS",
  "the-graph": "GRT",
  "near": "NEAR",
  "aptos": "APT",
  "arbitrum": "ARB",
  "optimism": "OP",
  "sui": "SUI",
  "pepe": "PEPE",
  "ton": "TON",
  "injective-protocol": "INJ",
  "sei-network": "SEI",
  "celestia": "TIA",
  "render-token": "RENDER",
  "fetch-ai": "FET",
  "worldcoin-wld": "WLD",
  "jupiter": "JUP",
  "bonk": "BONK",
  "dogwifcoin": "WIF",
  "floki": "FLOKI",
};

async function fetchFundingRates(): Promise<Map<string, number>> {
  const res = await fetch(BINANCE_FUTURES_API, {
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`Binance funding rates error: ${res.status}`);

  const raw = (await res.json()) as BinancePremiumIndex[];
  const map = new Map<string, number>();
  for (const item of raw) {
    const rate = parseFloat(item.lastFundingRate);
    if (!isNaN(rate)) map.set(item.symbol, rate);
  }
  return map;
}

async function getAll(): Promise<Map<string, number>> {
  const now = Date.now();
  if (cache && cache.expiresAt > now) return cache.data;
  if (!flight) {
    flight = fetchFundingRates()
      .then((data) => {
        cache = { data, expiresAt: Date.now() + CACHE_TTL_MS };
        flight = null;
        return data;
      })
      .catch((err) => {
        flight = null;
        logger.warn({ err }, "Failed to fetch Binance funding rates");
        return cache?.data ?? new Map();
      });
  }
  return flight;
}

export async function getFundingRate(
  coinId: string,
  symbol: string
): Promise<number | null> {
  try {
    const allRates = await getAll();
    const binanceSymbol =
      SYMBOL_MAP[coinId.toLowerCase()] ?? symbol.toUpperCase();
    const key = `${binanceSymbol}USDT`;
    const rate = allRates.get(key) ?? null;
    return rate;
  } catch {
    return null;
  }
}
