import { Link } from "wouter";
import { useGetMarketSummary, useGetTopSignals, useListCoins, useListSignals } from "@workspace/api-client-react";
import type { CoinSignal } from "@workspace/api-client-react/src/generated/api.schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowDownRight, ArrowUpRight, TrendingDown, TrendingUp, Activity, BarChart2, Layers } from "lucide-react";
import { useState } from "react";

export function SignalBadge({ signal, strength }: { signal: CoinSignal['signal'], strength: number }) {
  if (signal === "buy_long") {
    return (
      <Badge className="bg-[#10b981] hover:bg-[#10b981]/90 text-black font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm">
        <TrendingUp className="w-3 h-3 mr-1" /> BUY LONG [{strength}]
      </Badge>
    );
  }
  if (signal === "sell_short") {
    return (
      <Badge className="bg-[#e11d48] hover:bg-[#e11d48]/90 text-white font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm">
        <TrendingDown className="w-3 h-3 mr-1" /> SELL SHORT [{strength}]
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-muted-foreground font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm border-muted-foreground/30">
      NEUTRAL
    </Badge>
  );
}

function formatCurrency(val: number) {
  if (val >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(2)}M`;
  return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;
}

function MarketStats() {
  const { data: summary, isLoading, isError } = useGetMarketSummary();

  if (isLoading) return <Skeleton className="h-24 w-full rounded-md" />;
  if (isError || !summary) return <div className="p-4 border border-destructive/50 rounded-md text-destructive bg-destructive/10">Failed to load market summary</div>;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex flex-col justify-center h-full">
          <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider mb-1">Total MCap</div>
          <div className="text-xl font-bold font-mono">{formatCurrency(summary.total_market_cap_usd)}</div>
          <div className={`text-xs mt-1 flex items-center ${summary.market_cap_change_24h >= 0 ? 'text-[#10b981]' : 'text-[#e11d48]'}`}>
            {summary.market_cap_change_24h >= 0 ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            {Math.abs(summary.market_cap_change_24h).toFixed(2)}%
          </div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex flex-col justify-center h-full">
          <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider mb-1">24h Volume</div>
          <div className="text-xl font-bold font-mono">{formatCurrency(summary.total_volume_24h)}</div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex flex-col justify-center h-full">
          <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider mb-1">BTC Dominance</div>
          <div className="text-xl font-bold font-mono">{summary.btc_dominance.toFixed(1)}%</div>
        </CardContent>
      </Card>
      <Card className="bg-card/50 border-border/50">
        <CardContent className="p-4 flex flex-col justify-center h-full">
          <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider mb-1">Active Signals</div>
          <div className="flex gap-3 text-sm font-mono mt-1">
            <span className="text-[#10b981] font-bold">{summary.signal_counts.buy_long} L</span>
            <span className="text-muted-foreground">|</span>
            <span className="text-[#e11d48] font-bold">{summary.signal_counts.sell_short} S</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function TopSignals() {
  const { data: topSignals, isLoading } = useGetTopSignals();
  const { data: allSignals } = useListSignals();

  if (isLoading) return <Skeleton className="h-64 w-full rounded-md" />;
  if (!topSignals) return null;

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <Card className="border-[#10b981]/20 bg-[#10b981]/5">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm uppercase tracking-wider text-[#10b981] flex items-center">
            <TrendingUp className="w-4 h-4 mr-2" /> Top Buy Signals
          </CardTitle>
          <span className="text-xs text-muted-foreground font-mono">{allSignals?.buy_long.length || 0} Total</span>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {topSignals.top_buy_long.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4 text-center">No buy signals detected</div>
            ) : (
              topSignals.top_buy_long.map(coin => (
                <Link key={coin.id} href={`/coins/${coin.id}`}>
                  <div className="flex items-center justify-between p-2 rounded hover:bg-black/20 cursor-pointer transition-colors border border-transparent hover:border-[#10b981]/30">
                    <div className="flex items-center gap-3">
                      <img src={coin.image} alt={coin.name} className="w-8 h-8 rounded-full" />
                      <div>
                        <div className="font-bold font-mono text-sm">{coin.symbol.toUpperCase()}</div>
                        <div className="text-xs text-muted-foreground">{formatCurrency(coin.current_price)}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <SignalBadge signal={coin.signal} strength={coin.signal_strength} />
                      <div className="text-xs text-[#10b981] mt-1 font-mono">+{coin.price_change_percentage_24h?.toFixed(2)}%</div>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-[#e11d48]/20 bg-[#e11d48]/5">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm uppercase tracking-wider text-[#e11d48] flex items-center">
            <TrendingDown className="w-4 h-4 mr-2" /> Top Sell Signals
          </CardTitle>
          <span className="text-xs text-muted-foreground font-mono">{allSignals?.sell_short.length || 0} Total</span>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {topSignals.top_sell_short.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4 text-center">No sell signals detected</div>
            ) : (
              topSignals.top_sell_short.map(coin => (
                <Link key={coin.id} href={`/coins/${coin.id}`}>
                  <div className="flex items-center justify-between p-2 rounded hover:bg-black/20 cursor-pointer transition-colors border border-transparent hover:border-[#e11d48]/30">
                    <div className="flex items-center gap-3">
                      <img src={coin.image} alt={coin.name} className="w-8 h-8 rounded-full" />
                      <div>
                        <div className="font-bold font-mono text-sm">{coin.symbol.toUpperCase()}</div>
                        <div className="text-xs text-muted-foreground">{formatCurrency(coin.current_price)}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <SignalBadge signal={coin.signal} strength={coin.signal_strength} />
                      <div className="text-xs text-[#e11d48] mt-1 font-mono">{coin.price_change_percentage_24h?.toFixed(2)}%</div>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CoinTable() {
  const [filter, setFilter] = useState<"all" | "buy_long" | "sell_short" | "neutral">("all");
  const { data: coins, isLoading } = useListCoins({ 
    per_page: 50,
    signal: filter === "all" ? undefined : filter
  });

  return (
    <Card className="border-border/50 bg-card/50">
      <CardHeader className="pb-4 flex flex-row items-center justify-between">
        <CardTitle className="text-lg font-mono uppercase tracking-wider flex items-center gap-2">
          <Activity className="w-5 h-5 text-muted-foreground" /> Market Scanner
        </CardTitle>
        <Tabs value={filter} onValueChange={(v) => setFilter(v as any)} className="w-[400px]">
          <TabsList className="grid w-full grid-cols-4 bg-black/50 border border-border/50">
            <TabsTrigger value="all" className="text-xs uppercase font-mono">All</TabsTrigger>
            <TabsTrigger value="buy_long" className="text-xs uppercase font-mono text-[#10b981] data-[state=active]:bg-[#10b981]/20 data-[state=active]:text-[#10b981]">Long</TabsTrigger>
            <TabsTrigger value="sell_short" className="text-xs uppercase font-mono text-[#e11d48] data-[state=active]:bg-[#e11d48]/20 data-[state=active]:text-[#e11d48]">Short</TabsTrigger>
            <TabsTrigger value="neutral" className="text-xs uppercase font-mono">Neutral</TabsTrigger>
          </TabsList>
        </Tabs>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : !coins || coins.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground font-mono">No coins found matching criteria</div>
        ) : (
          <div className="rounded-md border border-border/50 overflow-hidden">
            <Table>
              <TableHeader className="bg-black/40">
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className="font-mono text-xs uppercase text-muted-foreground">Asset</TableHead>
                  <TableHead className="font-mono text-xs uppercase text-muted-foreground text-right">Price</TableHead>
                  <TableHead className="font-mono text-xs uppercase text-muted-foreground text-right">24h %</TableHead>
                  <TableHead className="font-mono text-xs uppercase text-muted-foreground text-right">Vol (24h)</TableHead>
                  <TableHead className="font-mono text-xs uppercase text-muted-foreground text-right">Signal</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {coins.map((coin) => (
                  <TableRow key={coin.id} className="border-border/50 hover:bg-muted/30 cursor-pointer group">
                    <TableCell className="py-3">
                      <Link href={`/coins/${coin.id}`} className="flex items-center gap-3">
                        <span className="text-muted-foreground text-xs font-mono w-4">{coin.market_cap_rank}</span>
                        <img src={coin.image} alt={coin.name} className="w-6 h-6 rounded-full" />
                        <div>
                          <div className="font-bold font-mono text-sm">{coin.symbol.toUpperCase()}</div>
                          <div className="text-xs text-muted-foreground">{coin.name}</div>
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell className="py-3 text-right font-mono text-sm">
                      {formatCurrency(coin.current_price)}
                    </TableCell>
                    <TableCell className="py-3 text-right font-mono text-sm">
                      <span className={!coin.price_change_percentage_24h ? "text-muted-foreground" : coin.price_change_percentage_24h > 0 ? "text-[#10b981]" : "text-[#e11d48]"}>
                        {coin.price_change_percentage_24h ? (
                          <span className="flex items-center justify-end">
                            {coin.price_change_percentage_24h > 0 ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                            {Math.abs(coin.price_change_percentage_24h).toFixed(2)}%
                          </span>
                        ) : "-"}
                      </span>
                    </TableCell>
                    <TableCell className="py-3 text-right font-mono text-sm text-muted-foreground">
                      {formatCurrency(coin.total_volume)}
                    </TableCell>
                    <TableCell className="py-3 text-right">
                      <SignalBadge signal={coin.signal} strength={coin.signal_strength} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  return (
    <div className="min-h-[100dvh] bg-background text-foreground pb-20">
      <header className="border-b border-border/50 bg-card/30 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-primary" />
            <h1 className="font-bold text-xl tracking-tight font-mono">CryptoDetect<span className="text-muted-foreground">.app</span></h1>
          </div>
          <div className="text-xs font-mono text-muted-foreground flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#10b981]"></span>
            </span>
            LIVE SIGNALS
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-6 space-y-6">
        <MarketStats />
        <TopSignals />
        <CoinTable />
      </main>
    </div>
  );
}