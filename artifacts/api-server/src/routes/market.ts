import { Router } from "express";
import { getMarkets, getGlobal } from "../lib/coinGeckoCache";
import { computeSignal } from "./coins";

const router = Router();

router.get("/market-summary", async (req, res) => {
  try {
    const [global, markets] = await Promise.all([getGlobal(), getMarkets(100)]);

    const counts = { buy_long: 0, sell_short: 0, neutral: 0 };
    for (const coin of markets) {
      const { signal } = computeSignal(coin);
      counts[signal]++;
    }

    res.json({
      total_market_cap_usd: global.data.total_market_cap.usd ?? 0,
      total_volume_24h: global.data.total_volume.usd ?? 0,
      btc_dominance: global.data.market_cap_percentage.btc ?? 0,
      market_cap_change_24h: global.data.market_cap_change_percentage_24h_usd ?? 0,
      signal_counts: counts,
    });
  } catch (err) {
    req.log.error({ err }, "Failed to fetch market summary");
    res.status(502).json({ error: "Failed to fetch market summary" });
  }
});

router.get("/top-signals", async (req, res) => {
  try {
    const markets = await getMarkets(100);

    const withSignals = markets.map((coin) => {
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
    });

    const buyLong = withSignals
      .filter((x) => x.signal === "buy_long")
      .sort((a, b) => b.signal_strength - a.signal_strength)
      .slice(0, 5);

    const sellShort = withSignals
      .filter((x) => x.signal === "sell_short")
      .sort((a, b) => a.signal_strength - b.signal_strength)
      .slice(0, 5);

    res.json({ top_buy_long: buyLong, top_sell_short: sellShort });
  } catch (err) {
    req.log.error({ err }, "Failed to fetch top signals");
    res.status(502).json({ error: "Failed to fetch top signals" });
  }
});

export default router;
