import { getMarkets, getMarketsWithSparkline, getGlobal, type CoinGeckoMarket } from "./coinGeckoCache";
import { computeSignal, computeSignalFull } from "../routes/coins";
import { logger } from "./logger";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const DEFAULT_CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const TELEGRAM_API = `https://api.telegram.org/bot${BOT_TOKEN}`;

let offset = 0;
let alertInterval: ReturnType<typeof setInterval> | null = null;
let pollTimeout: ReturnType<typeof setTimeout> | null = null;

// ─── Helpers ────────────────────────────────────────────────────────────────

async function tgFetch(method: string, body: Record<string, unknown>): Promise<unknown> {
  try {
    const res = await fetch(`${TELEGRAM_API}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  } catch (err) {
    logger.error({ err, method }, "Telegram API error");
    return null;
  }
}

async function sendMessage(chatId: string | number, text: string) {
  return tgFetch("sendMessage", {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
  });
}

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "N/A";
  return n.toFixed(decimals);
}

function fmtPrice(p: number): string {
  if (p >= 1) return `$${p.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  if (p >= 0.01) return `$${p.toFixed(4)}`;
  return `$${p.toFixed(8)}`;
}

function fmtBig(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

function signalEmoji(signal: string): string {
  if (signal === "buy_long") return "🟢";
  if (signal === "sell_short") return "🔴";
  return "⚪";
}

function changeEmoji(v: number | null): string {
  if (v == null) return "";
  return v >= 0 ? "▲" : "▼";
}

function buildStrengthBar(strength: number): string {
  const pct = (strength + 100) / 200;
  const filled = Math.round(pct * 10);
  const empty = 10 - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

function rsiLabel(rsi: number): string {
  if (rsi < 30) return "Oversold 🟢";
  if (rsi > 70) return "Overbought 🔴";
  return "Neutral ⚪";
}

function fundingLabel(rate: number): string {
  const pct = (rate * 100).toFixed(4);
  if (rate > 0.001) return `+${pct}% — longs paying (bearish) 🔴`;
  if (rate > 0) return `+${pct}% — mild long bias`;
  if (rate < -0.001) return `${pct}% — shorts paying (bullish) 🟢`;
  if (rate < 0) return `${pct}% — mild short bias`;
  return `${pct}% — neutral`;
}

// ─── Full coin message with TA ───────────────────────────────────────────────

async function buildFullCoinMessage(coin: CoinGeckoMarket): Promise<string> {
  const { signal, signal_strength, signal_reasons, ta, funding_rate } =
    await computeSignalFull(coin);

  const se = signalEmoji(signal);
  const label =
    signal === "buy_long" ? "BUY LONG" : signal === "sell_short" ? "SELL SHORT" : "NEUTRAL";
  const ch24 = coin.price_change_percentage_24h;
  const ch7d = coin.price_change_percentage_7d_in_currency;
  const bar = buildStrengthBar(signal_strength);

  const lines: string[] = [
    `${se} <b>${coin.name} (${coin.symbol.toUpperCase()})</b> — <b>${label}</b>`,
    ``,
    `💰 Price:  <b>${fmtPrice(coin.current_price)}</b>`,
    `📊 24h: <b>${changeEmoji(ch24)}${fmt(ch24)}%</b>   7d: <b>${changeEmoji(ch7d)}${fmt(ch7d)}%</b>`,
    `📦 Mkt Cap: <b>${fmtBig(coin.market_cap)}</b>   Rank #${coin.market_cap_rank}`,
    `💧 Volume:  <b>${fmtBig(coin.total_volume)}</b>`,
    ``,
  ];

  // ── Technical Indicators ───────────────────────────────────────────────────
  if (ta && (ta.rsi != null || ta.macd != null || ta.bb != null)) {
    lines.push(`📉 <b>Technical Indicators</b>`);
    if (ta.rsi != null) {
      lines.push(`  RSI(14):  <b>${ta.rsi}</b> — ${rsiLabel(ta.rsi)}`);
    }
    if (ta.macd != null) {
      const histDir = ta.macd.histogram >= 0 ? "▲ Bullish" : "▼ Bearish";
      lines.push(`  MACD:     Histogram <b>${ta.macd.histogram > 0 ? "+" : ""}${ta.macd.histogram.toExponential(2)}</b> — ${histDir}`);
    }
    if (ta.bb != null) {
      const pctB = (ta.bb.pctB * 100).toFixed(1);
      const bbLabel =
        ta.bb.pctB < 0.25 ? "Near lower band 🟢" : ta.bb.pctB > 0.75 ? "Near upper band 🔴" : "Mid-band ⚪";
      lines.push(`  BB %B:    <b>${pctB}%</b> — ${bbLabel}`);
    }
    lines.push(``);
  }

  // ── Funding Rate (Binance Futures) ─────────────────────────────────────────
  if (funding_rate != null) {
    lines.push(`💸 <b>Funding Rate (Binance)</b>`);
    lines.push(`  ${fundingLabel(funding_rate)}`);
    lines.push(``);
  }

  // ── Signal ─────────────────────────────────────────────────────────────────
  lines.push(`Signal Strength: ${bar} <b>${signal_strength > 0 ? "+" : ""}${signal_strength}</b>`);
  lines.push(``);
  lines.push(`<b>Signal Reasons:</b>`);
  for (const r of signal_reasons) lines.push(`• ${r}`);

  return lines.join("\n");
}

// ─── Market summary ──────────────────────────────────────────────────────────

async function buildMarketSummaryMessage(): Promise<string> {
  const [global, markets] = await Promise.all([getGlobal(), getMarkets(100)]);
  const counts = { buy_long: 0, sell_short: 0, neutral: 0 };
  for (const coin of markets) {
    const { signal } = computeSignal(coin);
    counts[signal]++;
  }
  const mc = global.data.total_market_cap.usd ?? 0;
  const vol = global.data.total_volume.usd ?? 0;
  const btc = global.data.market_cap_percentage.btc ?? 0;
  const change = global.data.market_cap_change_percentage_24h_usd ?? 0;

  return [
    `📈 <b>Market Summary</b>`,
    ``,
    `💰 Total Market Cap: <b>${fmtBig(mc)}</b> (${change >= 0 ? "▲" : "▼"}${fmt(change)}% 24h)`,
    `💧 24h Volume: <b>${fmtBig(vol)}</b>`,
    `₿ BTC Dominance: <b>${fmt(btc)}%</b>`,
    ``,
    `📊 Signals (top 100 coins):`,
    `🟢 Buy Long: <b>${counts.buy_long}</b>`,
    `🔴 Sell Short: <b>${counts.sell_short}</b>`,
    `⚪ Neutral: <b>${counts.neutral}</b>`,
  ].join("\n");
}

// ─── Top signals ─────────────────────────────────────────────────────────────

async function buildTopSignalsMessage(): Promise<string> {
  const markets = await getMarkets(100);
  const withSignals = markets.map((coin) => ({ coin, ...computeSignal(coin) }));

  const buyTop = withSignals
    .filter((x) => x.signal === "buy_long")
    .sort((a, b) => b.signal_strength - a.signal_strength)
    .slice(0, 5);

  const sellTop = withSignals
    .filter((x) => x.signal === "sell_short")
    .sort((a, b) => a.signal_strength - b.signal_strength)
    .slice(0, 5);

  const lines: string[] = [`🔍 <b>Top Signals Right Now</b>`, ``];

  if (buyTop.length) {
    lines.push(`🟢 <b>Top Buy Long</b>`);
    for (const x of buyTop) {
      const ch = x.coin.price_change_percentage_24h;
      lines.push(
        `  ${x.coin.name} (${x.coin.symbol.toUpperCase()}) — ${fmtPrice(x.coin.current_price)} ${changeEmoji(ch)}${fmt(ch)}% | Strength: +${x.signal_strength}`
      );
    }
    lines.push(``);
  }

  if (sellTop.length) {
    lines.push(`🔴 <b>Top Sell Short</b>`);
    for (const x of sellTop) {
      const ch = x.coin.price_change_percentage_24h;
      lines.push(
        `  ${x.coin.name} (${x.coin.symbol.toUpperCase()}) — ${fmtPrice(x.coin.current_price)} ${changeEmoji(ch)}${fmt(ch)}% | Strength: ${x.signal_strength}`
      );
    }
  }

  return lines.join("\n");
}

// ─── Command handler ─────────────────────────────────────────────────────────

async function handleCommand(chatId: number, text: string) {
  const [cmd, ...args] = text.trim().split(/\s+/);
  const command = cmd.toLowerCase().replace("@", " ").split(" ")[0];

  try {
    if (command === "/start" || command === "/help") {
      await sendMessage(
        chatId,
        [
          `🤖 <b>CryptoDetect Bot</b> — Powered by Binance + CoinGecko`,
          ``,
          `Commands:`,
          `/price &lt;coin&gt; — Full analysis: price, RSI, MACD, BB, funding rate`,
          `  e.g. <code>/price bitcoin</code>`,
          `/signals — Top Buy Long &amp; Sell Short coins`,
          `/market — Overall market summary`,
          `/top — Top 10 coins by market cap`,
          `/alert on — Auto alerts every 30 min`,
          `/alert off — Stop auto alerts`,
          `/help — Show this message`,
        ].join("\n")
      );
    } else if (command === "/price") {
      const query = args.join(" ").toLowerCase().trim();
      if (!query) {
        await sendMessage(chatId, "Usage: /price &lt;coin&gt;\nExample: /price bitcoin");
        return;
      }
      await sendMessage(chatId, `🔍 Fetching full analysis for <b>${query}</b>...`);

      const markets = await getMarketsWithSparkline();
      const coin =
        markets.find((c) => c.id === query) ||
        markets.find((c) => c.symbol.toLowerCase() === query) ||
        markets.find((c) => c.name.toLowerCase() === query) ||
        markets.find((c) => c.name.toLowerCase().includes(query) || c.id.includes(query));

      if (!coin) {
        await sendMessage(
          chatId,
          `❌ Coin "<b>${query}</b>" not found in top 250.\nTry: bitcoin, ethereum, solana, bnb, xrp`
        );
      } else {
        const msg = await buildFullCoinMessage(coin);
        await sendMessage(chatId, msg);
      }
    } else if (command === "/signals") {
      await sendMessage(chatId, await buildTopSignalsMessage());
    } else if (command === "/market") {
      await sendMessage(chatId, await buildMarketSummaryMessage());
    } else if (command === "/top") {
      const markets = await getMarkets(10);
      const lines = [`📊 <b>Top 10 Coins</b>`, ``];
      for (const coin of markets) {
        const { signal, signal_strength } = computeSignal(coin);
        const se = signalEmoji(signal);
        const ch = coin.price_change_percentage_24h;
        lines.push(
          `${se} #${coin.market_cap_rank} <b>${coin.name}</b> (${coin.symbol.toUpperCase()}) — ${fmtPrice(coin.current_price)} ${changeEmoji(ch)}${fmt(ch)}% | Strength: ${signal_strength > 0 ? "+" : ""}${signal_strength}`
        );
      }
      await sendMessage(chatId, lines.join("\n"));
    } else if (command === "/alert") {
      const sub = args[0]?.toLowerCase();
      if (sub === "on") {
        startAlerts(String(chatId));
        await sendMessage(chatId, "✅ Auto-alerts ON — signal updates every 30 minutes.");
      } else if (sub === "off") {
        stopAlerts();
        await sendMessage(chatId, "🔕 Auto-alerts OFF.");
      } else {
        await sendMessage(chatId, "Usage: /alert on  or  /alert off");
      }
    } else {
      await sendMessage(chatId, `Unknown command. Send /help to see all commands.`);
    }
  } catch (err) {
    logger.error({ err, command }, "Command handler error");
    await sendMessage(chatId, "❌ Something went wrong. Please try again in a moment.");
  }
}

// ─── Auto alerts ─────────────────────────────────────────────────────────────

function startAlerts(chatId: string) {
  if (alertInterval) clearInterval(alertInterval);
  alertInterval = setInterval(async () => {
    try {
      const msg = await buildTopSignalsMessage();
      await sendMessage(chatId, `🔔 <b>Signal Alert</b>\n\n${msg}`);
    } catch (err) {
      logger.error({ err }, "Alert send error");
    }
  }, 30 * 60 * 1000);
  logger.info({ chatId }, "Alert interval started");
}

function stopAlerts() {
  if (alertInterval) {
    clearInterval(alertInterval);
    alertInterval = null;
    logger.info("Alert interval stopped");
  }
}

// ─── Long polling ─────────────────────────────────────────────────────────────

async function poll() {
  try {
    const res = await fetch(
      `${TELEGRAM_API}/getUpdates?offset=${offset}&timeout=25&allowed_updates=["message"]`,
      { signal: AbortSignal.timeout(30_000) }
    );
    if (!res.ok) {
      logger.warn({ status: res.status }, "Telegram poll non-ok");
      schedulePoll(5000);
      return;
    }
    const data = (await res.json()) as { ok: boolean; result: TgUpdate[] };
    if (!data.ok) {
      schedulePoll(5000);
      return;
    }
    for (const update of data.result) {
      offset = update.update_id + 1;
      const msg = update.message;
      if (msg?.text && msg.text.startsWith("/")) {
        logger.info({ chat: msg.chat.id, text: msg.text }, "Bot command received");
        handleCommand(msg.chat.id, msg.text).catch(() => {});
      }
    }
  } catch (err: unknown) {
    if (err instanceof Error && err.name !== "TimeoutError") {
      logger.warn({ err }, "Telegram poll error");
    }
  }
  schedulePoll(100);
}

function schedulePoll(ms: number) {
  if (pollTimeout) clearTimeout(pollTimeout);
  pollTimeout = setTimeout(poll, ms);
}

interface TgUpdate {
  update_id: number;
  message?: { chat: { id: number }; text?: string };
}

// ─── Startup ──────────────────────────────────────────────────────────────────

export function startTelegramBot() {
  if (!BOT_TOKEN) {
    logger.warn("TELEGRAM_BOT_TOKEN not set — bot disabled");
    return;
  }

  logger.info("Starting Telegram bot (long polling) — powered by Binance + CoinGecko");
  schedulePoll(500);

  if (DEFAULT_CHAT_ID) {
    sendMessage(
      DEFAULT_CHAT_ID,
      [
        `🚀 <b>CryptoDetect Bot is online!</b>`,
        ``,
        `Powered by <b>Binance Futures</b> funding rates + <b>CoinGecko</b> price data`,
        ``,
        `/help — see all commands`,
        `/price bitcoin — full RSI, MACD, BB + funding rate analysis`,
        `/alert on — auto alerts every 30 min`,
      ].join("\n")
    ).catch(() => {});

    startAlerts(DEFAULT_CHAT_ID);
  }
}
