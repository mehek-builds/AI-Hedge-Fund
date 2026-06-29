"use client";

import { useEffect, useState, useCallback } from "react";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtCurrency, fmtPct, signClass } from "@/lib/format";
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip,
  LineChart, Line, ReferenceLine,
} from "recharts";

const STARTING_NAV = 1000;
const ALLOCATION_PER_POS = 190; // $190 each × 5 = $950 invested, $50 cash buffer

interface PositionMeta {
  ticker: string;
  allocation: number;
  sector: string;
  thesis: string;
  signal: string;
}

const POSITION_META: PositionMeta[] = [
  {
    ticker: "NVDA",
    allocation: ALLOCATION_PER_POS,
    sector: "Info Tech",
    thesis: "Data center AI beat · guidance raised · EPS gap +2.3σ",
    signal: "0.87",
  },
  {
    ticker: "AMD",
    allocation: ALLOCATION_PER_POS,
    sector: "Info Tech",
    thesis: "MI300X shipment acceleration · beat+raise · EPS gap +1.8σ",
    signal: "0.79",
  },
  {
    ticker: "GOOGL",
    allocation: ALLOCATION_PER_POS,
    sector: "Comm Svcs",
    thesis: "Cloud margin expansion · Search ad recovery · EPS gap +1.9σ",
    signal: "0.81",
  },
  {
    ticker: "AMZN",
    allocation: ALLOCATION_PER_POS,
    sector: "Cons Disc",
    thesis: "AWS re-acceleration · operating income beat · EPS gap +2.1σ",
    signal: "0.83",
  },
  {
    ticker: "UBER",
    allocation: ALLOCATION_PER_POS,
    sector: "Industrials",
    thesis: "EBITDA inflection · profitability beat · EPS gap +1.7σ",
    signal: "0.76",
  },
];

interface LivePrice {
  price: number;
  open: number;
  prevClose: number;
  price1hAgo: number;
  change: number;
  changePct: number;
  change1h: number;
  changePct1h: number;
  closes: number[];
  dates: string[];
  intradayTimestamps: number[];
  intradayPrices: number[];
}

type Prices = Record<string, LivePrice>;

function buildNavChart(prices: Prices, enriched: EnrichedPosition[]): { date: string; nav: number }[] {
  const allDates: string[] = [];
  for (const pos of enriched) {
    const d = prices[pos.ticker]?.dates ?? [];
    if (d.length > allDates.length) allDates.splice(0, allDates.length, ...d);
  }
  return allDates.map((date, i) => {
    let positionValue = 0;
    for (const pos of enriched) {
      const closes = prices[pos.ticker]?.closes ?? [];
      const closeAtDay = closes[i];
      positionValue += closeAtDay != null ? closeAtDay * pos.shares : pos.entryPrice * pos.shares;
    }
    const cash = STARTING_NAV - enriched.reduce((s, p) => s + p.entryPrice * p.shares, 0);
    return { date, nav: positionValue + Math.max(cash, 0) };
  });
}

interface EnrichedPosition extends PositionMeta {
  entryPrice: number;
  shares: number;
  currentPrice: number;
  unrealizedPnl: number;
  unrealizedPct: number;
  posValue: number;
  todayPnl1h: number;
}

export default function PaperTradingPage() {
  const [prices, setPrices] = useState<Prices>({});
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const fetchPrices = useCallback(async () => {
    const tickers = POSITION_META.map(p => p.ticker).join(",");
    try {
      const res = await fetch(`/api/prices?tickers=${tickers}`);
      if (!res.ok) return;
      const data: Prices = await res.json();
      setPrices(data);
      setLastUpdated(new Date().toLocaleTimeString("en-US", {
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
      }));
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    const id = setInterval(fetchPrices, 30_000);
    return () => clearInterval(id);
  }, [fetchPrices]);

  // Derive entry price from 1h-ago price; shares = floor(allocation / entry)
  const enriched: EnrichedPosition[] = POSITION_META.map(meta => {
    const live = prices[meta.ticker];
    const entryPrice = live?.price1hAgo ?? live?.open ?? 0;
    const shares = entryPrice > 0 ? Math.floor(meta.allocation / entryPrice) || 1 : 0;
    const currentPrice = live?.price ?? entryPrice;
    const unrealizedPnl = (currentPrice - entryPrice) * shares;
    const unrealizedPct = entryPrice > 0 ? ((currentPrice - entryPrice) / entryPrice) * 100 : 0;
    const posValue = currentPrice * shares;
    const todayPnl1h = (live?.change1h ?? 0) * shares;
    return { ...meta, entryPrice, shares, currentPrice, unrealizedPnl, unrealizedPct, posValue, todayPnl1h };
  });

  const costBasis = enriched.reduce((s, p) => s + p.entryPrice * p.shares, 0);
  const cash = Math.max(STARTING_NAV - costBasis, 0);
  const totalPosValue = enriched.reduce((s, p) => s + p.posValue, 0);
  const currentNav = totalPosValue + cash;
  const totalPnl = currentNav - STARTING_NAV;
  const totalPnlPct = (totalPnl / STARTING_NAV) * 100;
  const totalPnl1h = enriched.reduce((s, p) => s + p.todayPnl1h, 0);
  const totalPnl1hPct = (totalPnl1h / STARTING_NAV) * 100;

  const navChart = buildNavChart(prices, enriched);
  const navChartDisplay = navChart.length > 1 ? navChart : [];

  const isLoaded = !loading && enriched.some(p => p.entryPrice > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Stat row */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(6, 1fr)",
        borderBottom: "1px solid var(--color-border)",
        flexShrink: 0,
      }}>
        <StatCell label="Starting NAV" value={fmtCurrency(STARTING_NAV)} sub="Paper · today open" />
        <StatCell label="Current NAV" value={isLoaded ? fmtCurrency(currentNav) : "--"} sub={loading ? "loading…" : `updated ${lastUpdated}`} />
        <StatCell
          label="Total P&L"
          value={isLoaded ? fmtCurrency(totalPnl) : "--"}
          sub={isLoaded ? fmtPct(totalPnlPct) : ""}
          valueClass={signClass(totalPnl)}
        />
        <StatCell
          label="1h P&L"
          value={isLoaded ? fmtCurrency(totalPnl1h) : "--"}
          sub={isLoaded ? fmtPct(totalPnl1hPct) : "since entry"}
          valueClass={signClass(totalPnl1h)}
        />
        <StatCell label="Cash" value={isLoaded ? fmtCurrency(cash) : "--"} sub={isLoaded ? `${fmtPct((cash / STARTING_NAV) * 100)} of NAV` : ""} />
        <StatCell label="Positions" value={`${POSITION_META.length}`} sub="all long · 10d hold" />
      </div>

      {/* Body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}>

        {/* Left */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          <SectionHeader title="NAV performance" right="since today open · $1,000 start" />
          <div style={{ padding: "10px 12px 4px", flexShrink: 0, height: 110 }}>
            {navChartDisplay.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={navChartDisplay} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={totalPnl >= 0 ? "#22C55E" : "#EF4444"} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={totalPnl >= 0 ? "#22C55E" : "#EF4444"} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
                  <ReferenceLine y={STARTING_NAV} stroke="var(--color-text-muted)" strokeDasharray="3 3" strokeWidth={0.8} />
                  <Tooltip
                    contentStyle={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 4, fontSize: 11 }}
                    labelStyle={{ color: "var(--color-text-secondary)" }}
                    itemStyle={{ color: totalPnl >= 0 ? "var(--color-positive)" : "var(--color-negative)" }}
                    formatter={(v) => [typeof v === "number" ? `$${v.toFixed(2)}` : "--", "NAV"]}
                  />
                  <Area type="monotone" dataKey="nav" stroke={totalPnl >= 0 ? "#22C55E" : "#EF4444"} strokeWidth={1.5} fill="url(#navGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{loading ? "Fetching live prices…" : "Waiting for market data"}</span>
              </div>
            )}
          </div>

          {/* Position table */}
          <SectionHeader title="Open positions" right="paper · 5 active" />
          <div style={{
            display: "grid",
            gridTemplateColumns: "50px 42px 70px 70px 64px 64px 60px 52px 1fr",
            gap: 0, padding: "3px 10px",
            borderBottom: "1px solid var(--color-border)",
          }}>
            {["Ticker", "Shrs", "Entry 1h", "Current", "P&L $", "P&L %", "1h P&L", "Stop", "Thesis"].map(h => (
              <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: ["Shrs", "Entry 1h", "Current", "P&L $", "P&L %", "1h P&L", "Stop"].includes(h) ? "right" : "left" }}>{h}</span>
            ))}
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {enriched.map(pos => (
              <PositionRow key={pos.ticker} pos={pos} />
            ))}
          </div>

          {/* Summary row */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "50px 42px 70px 70px 64px 64px 60px 52px 1fr",
            gap: 0, padding: "4px 10px",
            borderTop: "1px solid var(--color-border)",
            background: "var(--color-bg-panel)",
          }}>
            <span className="num" style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Total</span>
            <span />
            <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>{isLoaded ? fmtCurrency(costBasis) : "--"}</span>
            <span className="num" style={{ fontSize: 9, textAlign: "right", color: "var(--color-text-primary)" }}>{isLoaded ? fmtCurrency(totalPosValue) : "--"}</span>
            <span className={`num ${signClass(totalPnl)}`} style={{ fontSize: 9, textAlign: "right" }}>{isLoaded ? fmtCurrency(totalPnl) : "--"}</span>
            <span className={`num ${signClass(totalPnlPct)}`} style={{ fontSize: 9, textAlign: "right" }}>{isLoaded ? fmtPct(totalPnlPct) : "--"}</span>
            <span className={`num ${signClass(totalPnl1h)}`} style={{ fontSize: 9, textAlign: "right" }}>{isLoaded ? fmtCurrency(totalPnl1h) : "--"}</span>
            <span /><span />
          </div>
        </div>

        {/* Right — sparklines */}
        <div style={{ width: 220, borderLeft: "1px solid var(--color-border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <SectionHeader title="Price action" right="10d" />
          <div style={{ flex: 1, overflowY: "auto" }}>
            {enriched.map(pos => (
              <TickerCard key={pos.ticker} pos={pos} prices={prices} />
            ))}
          </div>
          <div style={{ borderTop: "1px solid var(--color-border)", padding: "6px 10px" }}>
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginBottom: 4 }}>PAPER TRADE RULES</div>
            <div style={{ fontSize: 9, color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              $1,000 NAV · 10-day hold window · 8% hard stop<br />
              Entry = real price 1h ago · PEAD long bias<br />
              Prices refresh every 30s
            </div>
            <div style={{ marginTop: 6, fontSize: 9, color: "var(--color-text-muted)" }}>
              Expires: <span className="num" style={{ color: "var(--color-amber)" }}>2026-07-09</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function StatCell({ label, value, sub, valueClass }: {
  label: string; value: string; sub?: string; valueClass?: string;
}) {
  return (
    <div style={{ padding: "7px 12px", borderRight: "1px solid var(--color-border)" }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-text-muted)", marginBottom: 2 }}>{label}</div>
      <div className={`num ${valueClass ?? ""}`} style={{ fontSize: 15, fontWeight: 500 }}>{value}</div>
      {sub && <div className="num" style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

function PositionRow({ pos }: { pos: EnrichedPosition }) {
  const stopPrice = pos.entryPrice * 0.92;
  const atRisk = pos.entryPrice > 0 && pos.currentPrice <= stopPrice * 1.03;
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "50px 42px 70px 70px 64px 64px 60px 52px 1fr",
      alignItems: "center", gap: 0, padding: "4px 10px",
      borderBottom: "1px solid var(--color-border)",
      background: atRisk ? "rgba(239,68,68,0.04)" : undefined,
    }}>
      <span className="num" style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-primary)" }}>{pos.ticker}</span>
      <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{pos.shares || "--"}</span>
      <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(pos.entryPrice) : "--"}</span>
      <span className="num" style={{ fontSize: 10, textAlign: "right", color: "var(--color-text-primary)" }}>{pos.currentPrice > 0 ? fmtCurrency(pos.currentPrice) : "--"}</span>
      <span className={`num ${signClass(pos.unrealizedPnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(pos.unrealizedPnl) : "--"}</span>
      <span className={`num ${signClass(pos.unrealizedPct)}`} style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtPct(pos.unrealizedPct) : "--"}</span>
      <span className={`num ${signClass(pos.todayPnl1h)}`} style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(pos.todayPnl1h) : "--"}</span>
      <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(stopPrice) : "--"}</span>
      <span style={{ fontSize: 9, color: "var(--color-text-muted)", paddingLeft: 8, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{pos.sector}</span>
    </div>
  );
}

function TickerCard({ pos, prices }: {
  pos: EnrichedPosition;
  prices: Prices;
}) {
  const live = prices[pos.ticker];
  const closes = live?.closes ?? [];
  const chartData = closes.map((c, i) => ({ i, price: c }));
  const color = pos.unrealizedPnl >= 0 ? "#22C55E" : "#EF4444";

  return (
    <div style={{ borderBottom: "1px solid var(--color-border)", padding: "6px 10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span className="num" style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-primary)" }}>{pos.ticker}</span>
        <div style={{ textAlign: "right" }}>
          <span className="num" style={{ fontSize: 11, color: "var(--color-text-primary)" }}>{pos.currentPrice > 0 ? fmtCurrency(pos.currentPrice) : "--"}</span>
          <span className={`num ${signClass(pos.unrealizedPnl)}`} style={{ fontSize: 9, marginLeft: 6 }}>
            {pos.entryPrice > 0 ? `${pos.unrealizedPnl >= 0 ? "+" : ""}${fmtPct(pos.unrealizedPct)}` : ""}
          </span>
        </div>
      </div>
      {chartData.length > 1 && (
        <div style={{ height: 36 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <Line type="monotone" dataKey="price" stroke={color} strokeWidth={1.2} dot={false} />
              {pos.entryPrice > 0 && (
                <ReferenceLine y={pos.entryPrice} stroke="var(--color-text-muted)" strokeDasharray="2 2" strokeWidth={0.8} />
              )}
              <YAxis domain={["auto", "auto"]} hide />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <div style={{ fontSize: 8, color: "var(--color-text-muted)", marginTop: 3, lineHeight: 1.4 }}>
        {pos.entryPrice > 0 ? `Entry: ${fmtCurrency(pos.entryPrice)} · ${pos.shares} shr` : "loading entry…"}
        {" · "}{pos.thesis}
      </div>
    </div>
  );
}
