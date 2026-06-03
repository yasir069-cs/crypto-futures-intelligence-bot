const COINGECKO_BASE = "https://api.coingecko.com/api/v3";

const MARKETS_TTL_MS = 60_000;
const GLOBAL_TTL_MS = 90_000;

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
}

let marketsCache: CacheEntry<CoinGeckoMarket[]> | null = null;
let marketsSparklineCache: CacheEntry<CoinGeckoMarket[]> | null = null;
let globalCache: CacheEntry<CoinGeckoGlobal> | null = null;

let marketsFlight: Promise<CoinGeckoMarket[]> | null = null;
let marketsSparklineFlight: Promise<CoinGeckoMarket[]> | null = null;
let globalFlight: Promise<CoinGeckoGlobal> | null = null;

export interface CoinGeckoMarket {
  id: string;
  symbol: string;
  name: string;
  image: string;
  current_price: number;
  market_cap: number;
  market_cap_rank: number;
  price_change_percentage_24h: number | null;
  price_change_percentage_7d_in_currency: number | null;
  price_change_percentage_30d_in_currency: number | null;
  total_volume: number;
  ath: number | null;
  ath_change_percentage: number | null;
  circulating_supply: number | null;
  total_supply: number | null;
  sparkline_in_7d?: { price: number[] };
}

export interface CoinGeckoGlobal {
  data: {
    total_market_cap: Record<string, number>;
    total_volume: Record<string, number>;
    market_cap_percentage: Record<string, number>;
    market_cap_change_percentage_24h_usd: number;
  };
}

async function fetchFromCoinGecko<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`CoinGecko error: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function getMarkets(perPage = 250): Promise<CoinGeckoMarket[]> {
  const now = Date.now();
  if (marketsCache && marketsCache.expiresAt > now) return marketsCache.data;

  if (!marketsFlight) {
    const url = `${COINGECKO_BASE}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=${perPage}&page=1&price_change_percentage=24h,7d`;
    marketsFlight = fetchFromCoinGecko<CoinGeckoMarket[]>(url).then((data) => {
      marketsCache = { data, expiresAt: Date.now() + MARKETS_TTL_MS };
      marketsFlight = null;
      return data;
    }).catch((err) => {
      marketsFlight = null;
      throw err;
    });
  }

  return marketsFlight;
}

export async function getMarketsWithSparkline(): Promise<CoinGeckoMarket[]> {
  const now = Date.now();
  if (marketsSparklineCache && marketsSparklineCache.expiresAt > now) return marketsSparklineCache.data;

  if (!marketsSparklineFlight) {
    const url = `${COINGECKO_BASE}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&price_change_percentage=24h,7d,30d&sparkline=true`;
    marketsSparklineFlight = fetchFromCoinGecko<CoinGeckoMarket[]>(url).then((data) => {
      marketsSparklineCache = { data, expiresAt: Date.now() + MARKETS_TTL_MS };
      marketsSparklineFlight = null;
      return data;
    }).catch((err) => {
      marketsSparklineFlight = null;
      throw err;
    });
  }

  return marketsSparklineFlight;
}

export async function getGlobal(): Promise<CoinGeckoGlobal> {
  const now = Date.now();
  if (globalCache && globalCache.expiresAt > now) return globalCache.data;

  if (!globalFlight) {
    const url = `${COINGECKO_BASE}/global`;
    globalFlight = fetchFromCoinGecko<CoinGeckoGlobal>(url).then((data) => {
      globalCache = { data, expiresAt: Date.now() + GLOBAL_TTL_MS };
      globalFlight = null;
      return data;
    }).catch((err) => {
      globalFlight = null;
      throw err;
    });
  }

  return globalFlight;
}
