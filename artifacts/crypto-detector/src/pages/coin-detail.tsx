import { useRoute, Link } from "wouter";
import { useGetCoin } from "@workspace/api-client-react";
import { getGetCoinQueryKey } from "@workspace/api-client-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, ArrowDownRight, ArrowUpRight, Activity, TrendingUp, TrendingDown } from "lucide-react";
import { SignalBadge } from "./dashboard";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

function formatCurrency(val: number | null | undefined) {
  if (val === null || val === undefined) return "-";
  if (val >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(2)}M`;
  return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;
}

export default function CoinDetail() {
  const [, params] = useRoute("/coins/:id");
  const id = params?.id || "";

  const { data: coin, isLoading, isError } = useGetCoin(id, { 
    query: { 
      enabled: !!id, 
      queryKey: getGetCoinQueryKey(id) 
    } 
  });

  if (isLoading) {
    return (
      <div className="min-h-[100dvh] bg-background text-foreground p-6">
        <div className="container mx-auto max-w-4xl space-y-6">
          <Skeleton className="h-8 w-24 mb-6" />
          <Skeleton className="h-32 w-full rounded-lg" />
          <div className="grid md:grid-cols-3 gap-6">
            <Skeleton className="h-64 md:col-span-2 rounded-lg" />
            <Skeleton className="h-64 rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  if (isError || !coin) {
    return (
      <div className="min-h-[100dvh] bg-background flex flex-col items-center justify-center p-6 text-center">
        <Activity className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
        <h2 className="text-xl font-mono font-bold mb-2">Asset Not Found</h2>
        <p className="text-muted-foreground mb-6">Could not load details for this asset.</p>
        <Link href="/" className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm font-mono font-bold hover:bg-primary/90 transition-colors">
          RETURN TO SCANNER
        </Link>
      </div>
    );
  }

  const chartData = coin.sparkline_in_7d.map((val, i) => ({ price: val, index: i }));
  const isUp = coin.price_change_percentage_7d_in_currency && coin.price_change_percentage_7d_in_currency >= 0;
  const strokeColor = isUp ? "#10b981" : "#e11d48";

  return (
    <div className="min-h-[100dvh] bg-background text-foreground pb-20">
      <header className="border-b border-border/50 bg-card/30 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 h-14 flex items-center">
          <Link href="/" className="text-muted-foreground hover:text-foreground flex items-center text-sm font-mono transition-colors">
            <ArrowLeft className="w-4 h-4 mr-2" /> Back to Scanner
          </Link>
        </div>
      </header>

      <main className="container mx-auto max-w-5xl px-4 py-6 space-y-6">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 bg-card/30 p-6 rounded-lg border border-border/50">
          <div className="flex items-center gap-4">
            <img src={coin.image} alt={coin.name} className="w-16 h-16 rounded-full" />
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-bold font-mono tracking-tight">{coin.name}</h1>
                <span className="text-sm px-2 py-0.5 rounded bg-muted/50 text-muted-foreground font-mono font-bold uppercase">{coin.symbol}</span>
                <span className="text-xs px-2 py-0.5 rounded border border-border text-muted-foreground font-mono">Rank #{coin.market_cap_rank}</span>
              </div>
              <div className="text-3xl font-mono font-bold">
                {formatCurrency(coin.current_price)}
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-3">
            <SignalBadge signal={coin.signal} strength={coin.signal_strength} />
            <div className="flex gap-4 text-sm font-mono">
              <div className="flex flex-col items-end">
                <span className="text-xs text-muted-foreground">24H</span>
                <span className={!coin.price_change_percentage_24h ? "text-muted-foreground" : coin.price_change_percentage_24h >= 0 ? "text-[#10b981]" : "text-[#e11d48]"}>
                  {coin.price_change_percentage_24h?.toFixed(2)}%
                </span>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-xs text-muted-foreground">7D</span>
                <span className={!coin.price_change_percentage_7d_in_currency ? "text-muted-foreground" : coin.price_change_percentage_7d_in_currency >= 0 ? "text-[#10b981]" : "text-[#e11d48]"}>
                  {coin.price_change_percentage_7d_in_currency?.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Chart Section */}
          <Card className="md:col-span-2 bg-card/50 border-border/50">
            <CardHeader className="pb-2 border-b border-border/50 mb-4">
              <CardTitle className="text-sm uppercase font-mono text-muted-foreground">7-Day Price Action</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <YAxis domain={['auto', 'auto']} hide />
                    <Line 
                      type="monotone" 
                      dataKey="price" 
                      stroke={strokeColor} 
                      strokeWidth={2} 
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Details Section */}
          <div className="space-y-6">
            <Card className={`border-border/50 ${
              coin.signal === 'buy_long' ? 'bg-[#10b981]/5 border-[#10b981]/30' :
              coin.signal === 'sell_short' ? 'bg-[#e11d48]/5 border-[#e11d48]/30' :
              'bg-card/50'
            }`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm uppercase font-mono text-muted-foreground flex items-center">
                  <Activity className="w-4 h-4 mr-2" /> Signal Intelligence
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <div className="text-xs text-muted-foreground uppercase font-mono mb-1">Strength</div>
                  <div className="flex items-center gap-2">
                    <div className="h-2 flex-1 bg-black/50 rounded overflow-hidden">
                      <div 
                        className={`h-full ${coin.signal_strength > 0 ? 'bg-[#10b981]' : 'bg-[#e11d48]'}`} 
                        style={{ width: `${Math.abs(coin.signal_strength)}%`, marginLeft: coin.signal_strength < 0 ? 'auto' : '0' }}
                      />
                    </div>
                    <span className="text-xs font-mono font-bold w-8 text-right">{coin.signal_strength}</span>
                  </div>
                </div>
                
                <div>
                  <div className="text-xs text-muted-foreground uppercase font-mono mb-2">Drivers</div>
                  <ul className="space-y-2">
                    {coin.signal_reasons.length === 0 ? (
                      <li className="text-xs text-muted-foreground italic">No specific drivers</li>
                    ) : (
                      coin.signal_reasons.map((reason, i) => (
                        <li key={i} className="text-sm font-mono flex items-start gap-2">
                          <span className={`mt-0.5 ${coin.signal === 'buy_long' ? 'text-[#10b981]' : coin.signal === 'sell_short' ? 'text-[#e11d48]' : 'text-muted-foreground'}`}>
                            {coin.signal === 'buy_long' ? <TrendingUp className="w-4 h-4" /> : coin.signal === 'sell_short' ? <TrendingDown className="w-4 h-4" /> : <Activity className="w-4 h-4" />}
                          </span>
                          <span className="leading-tight opacity-90">{reason}</span>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card/50 border-border/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm uppercase font-mono text-muted-foreground">Market Data</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center py-1 border-b border-border/30">
                  <span className="text-xs text-muted-foreground uppercase font-mono">Market Cap</span>
                  <span className="text-sm font-mono font-bold">{formatCurrency(coin.market_cap)}</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-border/30">
                  <span className="text-xs text-muted-foreground uppercase font-mono">Volume (24h)</span>
                  <span className="text-sm font-mono font-bold">{formatCurrency(coin.total_volume)}</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-border/30">
                  <span className="text-xs text-muted-foreground uppercase font-mono">Circ. Supply</span>
                  <span className="text-sm font-mono">{coin.circulating_supply ? coin.circulating_supply.toLocaleString() : "-"}</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-border/30">
                  <span className="text-xs text-muted-foreground uppercase font-mono">Total Supply</span>
                  <span className="text-sm font-mono">{coin.total_supply ? coin.total_supply.toLocaleString() : "-"}</span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-xs text-muted-foreground uppercase font-mono">All Time High</span>
                  <div className="text-right">
                    <div className="text-sm font-mono font-bold">{formatCurrency(coin.ath)}</div>
                    <div className="text-xs font-mono text-[#e11d48]">{coin.ath_change_percentage?.toFixed(2)}%</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}