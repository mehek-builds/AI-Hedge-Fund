"use client";

import { useEffect, useState, useCallback } from "react";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtCurrency, fmtPct, signClass } from "@/lib/format";
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip,
  LineChart, Line, ReferenceLine,
} from "recharts";

// ── Long book ────────────────────────────────────────────────────────────────
const LONG_NAV = 1000;
const LONG_ALLOC = 95; // $95 × 10 = $950, $50 cash

interface PositionMeta {
  ticker: string;
  allocation: number;
  sector: string;
  thesis: string;
  signal: string;
  type: "PEAD" | "WATCH";
}

const LONG_META: PositionMeta[] = [
  { ticker: "MU",    allocation: LONG_ALLOC, sector: "Info Tech",   signal: "0.91", type: "PEAD", thesis: "Q3 2026: EPS $25.11 vs $20.71 est (+21.2%) · reported Jun 25 · pulled back 7% post-earnings, drift pending" },
  { ticker: "CRM",   allocation: LONG_ALLOC, sector: "Info Tech",   signal: "0.89", type: "PEAD", thesis: "Q1 2026: EPS $3.88 vs $3.13 est (+24.1%) · reported May 28 · largest beat on board, price still suppressed" },
  { ticker: "SNOW",  allocation: LONG_ALLOC, sector: "Info Tech",   signal: "0.86", type: "PEAD", thesis: "Q1 2026: EPS $0.39 vs $0.32 est (+21.9%) · reported May 28 · drift started +5.3%, still early" },
  { ticker: "TGT",   allocation: LONG_ALLOC, sector: "Cons Disc",   signal: "0.82", type: "PEAD", thesis: "Q1 2026: EPS $1.71 vs $1.46 est (+17.3%) · reported May 20 · drift confirmed +11% in 40 days" },
  { ticker: "DE",    allocation: LONG_ALLOC, sector: "Industrials", signal: "0.78", type: "PEAD", thesis: "Q2 2026: EPS $6.55 vs $5.74 est (+14.1%) · reported May 15 · drift confirmed +10% in 45 days" },
  { ticker: "NVDA",  allocation: LONG_ALLOC, sector: "Info Tech",   signal: "0.72", type: "WATCH", thesis: "Q1 2026: EPS $1.87 vs $1.77 est (+5.5%) · reported May 28 · sold off post-earnings, watching for reversal" },
  { ticker: "AMD",   allocation: LONG_ALLOC, sector: "Info Tech",   signal: "0.65", type: "WATCH", thesis: "MI300X AI GPU ramp · no Q1 2026 earnings in PEAD window · momentum position" },
  { ticker: "GOOGL", allocation: LONG_ALLOC, sector: "Comm Svcs",   signal: "0.63", type: "WATCH", thesis: "Cloud + Search ad recovery · no recent earnings beat in PEAD window · momentum position" },
  { ticker: "AMZN",  allocation: LONG_ALLOC, sector: "Cons Disc",   signal: "0.64", type: "WATCH", thesis: "AWS re-acceleration · no recent earnings beat in PEAD window · momentum position" },
  { ticker: "UBER",  allocation: LONG_ALLOC, sector: "Industrials", signal: "0.61", type: "WATCH", thesis: "EBITDA inflection · no recent earnings beat in PEAD window · momentum position" },
];

// ── Puts book ─────────────────────────────────────────────────────────────────
const PUT_NAV = 1000;
const PUT_ALLOC = 200; // $200 × 5 = $1,000

interface PutMeta {
  ticker: string;
  allocation: number;
  sector: string;
  thesis: string;
}

const PUT_META: PutMeta[] = [
  { ticker: "SOXX", allocation: PUT_ALLOC, sector: "Semi ETF",    thesis: "AI capex slowdown risk · cycle peak valuation · semi equipment deceleration concerns" },
  { ticker: "QQQ",  allocation: PUT_ALLOC, sector: "Nasdaq ETF",  thesis: "Rate sensitivity · stretched mega-cap valuations · potential multiple compression" },
  { ticker: "PLTR", allocation: PUT_ALLOC, sector: "Info Tech",   thesis: "Government contract concentration risk · 60x+ revenue multiple · insider selling pressure" },
  { ticker: "NVDA", allocation: PUT_ALLOC, sector: "Info Tech",   thesis: "Hedge vs long book · -9.4% post-earnings despite beat · export restriction overhang" },
  { ticker: "ORCL", allocation: PUT_ALLOC, sector: "Info Tech",   thesis: "Guidance miss drove -26% post-earnings · cloud transition slower than expected · further downside risk" },
];

// All unique tickers across both books
const ALL_TICKERS = [...new Set([...LONG_META.map(p => p.ticker), ...PUT_META.map(p => p.ticker)])];

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
}

type Prices = Record<string, LivePrice>;

interface EnrichedLong extends PositionMeta {
  entryPrice: number;
  shares: number;
  currentPrice: number;
  unrealizedPnl: number;
  unrealizedPct: number;
  posValue: number;
  dayPnl: number;
}

interface EnrichedPut extends PutMeta {
  entryUnderlying: number;
  currentUnderlying: number;
  // P&L modeled as ATM put with delta = -0.5; gains when underlying falls
  putPnl: number;
  putPct: number;
  currentValue: number;
  dayPnl: number;
}

function buildNavChart(prices: Prices, enriched: EnrichedLong[]): { date: string; nav: number }[] {
  const allDates: string[] = [];
  for (const pos of enriched) {
    const d = prices[pos.ticker]?.dates ?? [];
    if (d.length > allDates.length) allDates.splice(0, allDates.length, ...d);
  }
  const cash = LONG_NAV - enriched.reduce((s, p) => s + p.entryPrice * p.shares, 0);
  return allDates.map((date, i) => {
    let posVal = 0;
    for (const pos of enriched) {
      const closes = prices[pos.ticker]?.closes ?? [];
      posVal += (closes[i] != null ? closes[i] : pos.entryPrice) * pos.shares;
    }
    return { date, nav: posVal + Math.max(cash, 0) };
  });
}

export default function PaperTradingPage() {
  const [prices, setPrices] = useState<Prices>({});
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const fetchPrices = useCallback(async () => {
    try {
      const res = await fetch(`/api/prices?tickers=${ALL_TICKERS.join(",")}`);
      if (!res.ok) return;
      const data: Prices = await res.json();
      setPrices(data);
      setLastUpdated(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
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

  // ── Enrich longs ──
  const longs: EnrichedLong[] = LONG_META.map(meta => {
    const live = prices[meta.ticker];
    const entryPrice = live?.price1hAgo ?? live?.open ?? 0;
    const shares = entryPrice > 0 ? meta.allocation / entryPrice : 0;
    const currentPrice = live?.price ?? entryPrice;
    const unrealizedPnl = (currentPrice - entryPrice) * shares;
    const unrealizedPct = entryPrice > 0 ? ((currentPrice - entryPrice) / entryPrice) * 100 : 0;
    const posValue = currentPrice * shares;
    const dayPnl = (live?.change ?? 0) * shares;
    return { ...meta, entryPrice, shares, currentPrice, unrealizedPnl, unrealizedPct, posValue, dayPnl };
  });

  const longCostBasis = longs.reduce((s, p) => s + p.entryPrice * p.shares, 0);
  const longCash = Math.max(LONG_NAV - longCostBasis, 0);
  const longPosValue = longs.reduce((s, p) => s + p.posValue, 0);
  const longCurrentNav = longPosValue + longCash;
  const longTotalPnl = longCurrentNav - LONG_NAV;
  const longTotalPnlPct = (longTotalPnl / LONG_NAV) * 100;
  const longDayPnl = longs.reduce((s, p) => s + p.dayPnl, 0);
  const longDayPnlPct = (longDayPnl / LONG_NAV) * 100;

  // ── Enrich puts ──
  // Model: ATM put delta = -0.5 · P&L = -0.5 × (current - entry) / entry × allocation
  // i.e. underlying down 1% → put up 0.5% of allocation
  const puts: EnrichedPut[] = PUT_META.map(meta => {
    const live = prices[meta.ticker];
    const entryUnderlying = live?.price1hAgo ?? live?.open ?? 0;
    const currentUnderlying = live?.price ?? entryUnderlying;
    const underlyingReturn = entryUnderlying > 0 ? (currentUnderlying - entryUnderlying) / entryUnderlying : 0;
    const putPnl = -0.5 * underlyingReturn * meta.allocation;
    const putPct = -0.5 * underlyingReturn * 100;
    const currentValue = meta.allocation + putPnl;
    const dayUnderlyingReturn = entryUnderlying > 0 ? (live?.change ?? 0) / entryUnderlying : 0;
    const dayPnl = -0.5 * dayUnderlyingReturn * meta.allocation;
    return { ...meta, entryUnderlying, currentUnderlying, putPnl, putPct, currentValue, dayPnl };
  });

  const putCostBasis = PUT_META.reduce((s, p) => s + p.allocation, 0);
  const putCurrentValue = puts.reduce((s, p) => s + p.currentValue, 0);
  const putTotalPnl = putCurrentValue - PUT_NAV;
  const putTotalPnlPct = (putTotalPnl / PUT_NAV) * 100;
  const putDayPnl = puts.reduce((s, p) => s + p.dayPnl, 0);
  const putDayPnlPct = (putDayPnl / PUT_NAV) * 100;

  // ── Combined ──
  const combinedNav = longCurrentNav + putCurrentValue;
  const combinedPnl = longTotalPnl + putTotalPnl;
  const combinedPnlPct = (combinedPnl / (LONG_NAV + PUT_NAV)) * 100;

  const navChart = buildNavChart(prices, longs);
  const isLoaded = !loading && longs.some(p => p.entryPrice > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Combined header strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", borderBottom: "1px solid var(--color-border)", flexShrink: 0 }}>
        <StatCell label="Total NAV" value={isLoaded ? fmtCurrency(combinedNav, 2) : "--"} sub="longs + puts" />
        <StatCell label="Combined P&L" value={isLoaded ? fmtCurrency(combinedPnl, 2) : "--"} sub={isLoaded ? fmtPct(combinedPnlPct) : ""} valueClass={signClass(combinedPnl)} />
        <StatCell label="Long NAV" value={isLoaded ? fmtCurrency(longCurrentNav, 2) : "--"} sub={isLoaded ? fmtPct(longTotalPnlPct) : "$1,000 start"} valueClass={signClass(longTotalPnl)} />
        <StatCell label="Puts NAV" value={isLoaded ? fmtCurrency(putCurrentValue, 2) : "--"} sub={isLoaded ? fmtPct(putTotalPnlPct) : "$1,000 start"} valueClass={signClass(putTotalPnl)} />
        <StatCell label="Day P&L" value={isLoaded ? fmtCurrency(longDayPnl + putDayPnl, 2) : "--"} sub={isLoaded ? fmtPct((longDayPnl + putDayPnl) / 2000 * 100) : "vs prev close"} valueClass={signClass(longDayPnl + putDayPnl)} />
        <StatCell label="Positions" value={`${LONG_META.length}L + ${PUT_META.length}P`} sub="all paper · 30s refresh" />
      </div>

      {/* Body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}>

        {/* Left column */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

          {/* NAV chart */}
          <SectionHeader title="Long book NAV" right={`since today open · $${LONG_NAV} start`} />
          <div style={{ padding: "10px 12px 4px", flexShrink: 0, height: 90 }}>
            {navChart.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={navChart} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={longTotalPnl >= 0 ? "#22C55E" : "#EF4444"} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={longTotalPnl >= 0 ? "#22C55E" : "#EF4444"} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
                  <ReferenceLine y={LONG_NAV} stroke="var(--color-text-muted)" strokeDasharray="3 3" strokeWidth={0.8} />
                  <Tooltip contentStyle={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 4, fontSize: 11 }} formatter={(v) => [typeof v === "number" ? `$${v.toFixed(2)}` : "--", "NAV"]} />
                  <Area type="monotone" dataKey="nav" stroke={longTotalPnl >= 0 ? "#22C55E" : "#EF4444"} strokeWidth={1.5} fill="url(#navGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{loading ? "Fetching prices…" : "Waiting for market data"}</span>
              </div>
            )}
          </div>

          {/* Long table */}
          <SectionHeader title="Long positions" right={`${LONG_META.length} active · 5 PEAD + 5 WATCH · ${isLoaded ? fmtCurrency(longCurrentNav, 2) : "$1,000.00"}`} />
          <TableHeader cols={["Ticker", "Shrs", "Entry", "Current", "P&L $", "P&L %", "Day", "Stop", "Thesis"]} />
          <div style={{ flex: "0 0 auto", overflowY: "auto", maxHeight: 220 }}>
            {longs.map(pos => <LongRow key={pos.ticker} pos={pos} />)}
          </div>
          <TotalsRow
            label="Longs"
            col3={isLoaded ? fmtCurrency(longCostBasis, 2) : "--"}
            col4={isLoaded ? fmtCurrency(longPosValue, 2) : "--"}
            col5={{ val: longTotalPnl, fmt: isLoaded ? fmtCurrency(longTotalPnl, 2) : "--" }}
            col6={{ val: longTotalPnlPct, fmt: isLoaded ? fmtPct(longTotalPnlPct) : "--" }}
            col7={{ val: longDayPnl, fmt: isLoaded ? fmtCurrency(longDayPnl, 2) : "--" }}
          />

          {/* Puts table */}
          <SectionHeader title="Put positions" right={`${PUT_META.length} active · ATM delta -0.5 model · ${isLoaded ? fmtCurrency(putCurrentValue, 2) : "$1,000.00"}`} accent="var(--color-negative)" />
          <TableHeader cols={["Ticker", "Alloc", "Underlying", "Now", "Put P&L", "P&L %", "Day", "Model", "Thesis"]} />
          <div style={{ flex: "0 0 auto", overflowY: "auto", maxHeight: 180 }}>
            {puts.map(pos => <PutRow key={pos.ticker} pos={pos} isLoaded={isLoaded} />)}
          </div>
          <TotalsRow
            label="Puts"
            col3={fmtCurrency(putCostBasis, 2)}
            col4={isLoaded ? fmtCurrency(putCurrentValue, 2) : "--"}
            col5={{ val: putTotalPnl, fmt: isLoaded ? fmtCurrency(putTotalPnl, 2) : "--" }}
            col6={{ val: putTotalPnlPct, fmt: isLoaded ? fmtPct(putTotalPnlPct) : "--" }}
            col7={{ val: putDayPnl, fmt: isLoaded ? fmtCurrency(putDayPnl, 2) : "--" }}
          />
        </div>

        {/* Right — sparklines */}
        <div style={{ width: 210, borderLeft: "1px solid var(--color-border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <SectionHeader title="Longs" right="10d" />
          <div style={{ flex: 1, overflowY: "auto" }}>
            {longs.map(pos => <SparkCard key={pos.ticker} ticker={pos.ticker} label={pos.type} labelColor={pos.type === "PEAD" ? "var(--color-amber)" : "var(--color-text-muted)"} currentPrice={pos.currentPrice} pct={pos.unrealizedPct} entryPrice={pos.entryPrice} closes={prices[pos.ticker]?.closes ?? []} pnlSign={pos.unrealizedPnl} />)}
            <div style={{ borderTop: "2px solid var(--color-border)", padding: "3px 10px", background: "rgba(239,68,68,0.03)" }}>
              <span style={{ fontSize: 9, color: "var(--color-negative)", fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" }}>Puts</span>
            </div>
            {puts.map(pos => <SparkCard key={`put-${pos.ticker}`} ticker={pos.ticker} label="PUT" labelColor="var(--color-negative)" currentPrice={pos.currentUnderlying} pct={pos.putPct} entryPrice={pos.entryUnderlying} closes={prices[pos.ticker]?.closes ?? []} pnlSign={pos.putPnl} invertArrow />)}
          </div>
          <div style={{ borderTop: "1px solid var(--color-border)", padding: "6px 10px", flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginBottom: 4 }}>MODEL</div>
            <div style={{ fontSize: 9, color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              Longs: fractional shares, 8% stop<br />
              Puts: ATM delta -0.5, premium = alloc<br />
              Both refresh every 30s
            </div>
            <div style={{ marginTop: 4, fontSize: 9, color: "var(--color-text-muted)" }}>
              Expires <span className="num" style={{ color: "var(--color-amber)" }}>2026-07-09</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCell({ label, value, sub, valueClass }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <div style={{ padding: "7px 12px", borderRight: "1px solid var(--color-border)" }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-text-muted)", marginBottom: 2 }}>{label}</div>
      <div className={`num ${valueClass ?? ""}`} style={{ fontSize: 14, fontWeight: 500 }}>{value}</div>
      {sub && <div className="num" style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

const COL = "50px 44px 70px 70px 64px 60px 56px 52px 1fr";

function TableHeader({ cols }: { cols: string[] }) {
  const rightAligned = cols.slice(1, 8);
  return (
    <div style={{ display: "grid", gridTemplateColumns: COL, padding: "3px 10px", borderBottom: "1px solid var(--color-border)" }}>
      {cols.map(h => (
        <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: rightAligned.includes(h) ? "right" : "left" }}>{h}</span>
      ))}
    </div>
  );
}

function TotalsRow({ label, col3, col4, col5, col6, col7 }: {
  label: string;
  col3: string; col4: string;
  col5: { val: number; fmt: string };
  col6: { val: number; fmt: string };
  col7: { val: number; fmt: string };
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: COL, padding: "4px 10px", borderTop: "1px solid var(--color-border)", background: "var(--color-bg-panel)", flexShrink: 0 }}>
      <span style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase" }}>{label}</span>
      <span />
      <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>{col3}</span>
      <span className="num" style={{ fontSize: 9, textAlign: "right", color: "var(--color-text-primary)" }}>{col4}</span>
      <span className={`num ${signClass(col5.val)}`} style={{ fontSize: 9, textAlign: "right" }}>{col5.fmt}</span>
      <span className={`num ${signClass(col6.val)}`} style={{ fontSize: 9, textAlign: "right" }}>{col6.fmt}</span>
      <span className={`num ${signClass(col7.val)}`} style={{ fontSize: 9, textAlign: "right" }}>{col7.fmt}</span>
      <span /><span />
    </div>
  );
}

function LongRow({ pos }: { pos: EnrichedLong }) {
  const stopPrice = pos.entryPrice * 0.92;
  const atRisk = pos.entryPrice > 0 && pos.currentPrice <= stopPrice * 1.03;
  return (
    <div style={{ display: "grid", gridTemplateColumns: COL, alignItems: "center", padding: "4px 10px", borderBottom: "1px solid var(--color-border)", background: atRisk ? "rgba(239,68,68,0.04)" : undefined }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <span className="num" style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-primary)" }}>{pos.ticker}</span>
        <span style={{ fontSize: 7, fontWeight: 600, color: pos.type === "PEAD" ? "var(--color-amber)" : "var(--color-text-muted)" }}>{pos.type}</span>
      </div>
      <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>{pos.shares > 0 ? pos.shares.toFixed(3) : "--"}</span>
      <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(pos.entryPrice, 2) : "--"}</span>
      <span className="num" style={{ fontSize: 10, textAlign: "right", color: "var(--color-text-primary)" }}>{pos.currentPrice > 0 ? fmtCurrency(pos.currentPrice, 2) : "--"}</span>
      <span className={`num ${signClass(pos.unrealizedPnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(pos.unrealizedPnl, 2) : "--"}</span>
      <span className={`num ${signClass(pos.unrealizedPct)}`} style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtPct(pos.unrealizedPct) : "--"}</span>
      <span className={`num ${signClass(pos.dayPnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(pos.dayPnl, 2) : "--"}</span>
      <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>{pos.entryPrice > 0 ? fmtCurrency(stopPrice, 2) : "--"}</span>
      <span style={{ fontSize: 9, color: "var(--color-text-muted)", paddingLeft: 8, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{pos.sector}</span>
    </div>
  );
}

function PutRow({ pos, isLoaded }: { pos: EnrichedPut; isLoaded: boolean }) {
  const inProfit = pos.putPnl > 0;
  return (
    <div style={{ display: "grid", gridTemplateColumns: COL, alignItems: "center", padding: "4px 10px", borderBottom: "1px solid var(--color-border)", background: inProfit ? "rgba(34,197,94,0.03)" : "rgba(239,68,68,0.03)" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <span className="num" style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-primary)" }}>{pos.ticker}</span>
        <span style={{ fontSize: 7, fontWeight: 600, color: "var(--color-negative)" }}>PUT</span>
      </div>
      <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>{fmtCurrency(pos.allocation)}</span>
      <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{isLoaded && pos.entryUnderlying > 0 ? fmtCurrency(pos.entryUnderlying, 2) : "--"}</span>
      <span className="num" style={{ fontSize: 10, textAlign: "right", color: "var(--color-text-primary)" }}>{isLoaded && pos.currentUnderlying > 0 ? fmtCurrency(pos.currentUnderlying, 2) : "--"}</span>
      <span className={`num ${signClass(pos.putPnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{isLoaded ? fmtCurrency(pos.putPnl, 2) : "--"}</span>
      <span className={`num ${signClass(pos.putPct)}`} style={{ fontSize: 10, textAlign: "right" }}>{isLoaded ? fmtPct(pos.putPct) : "--"}</span>
      <span className={`num ${signClass(pos.dayPnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{isLoaded ? fmtCurrency(pos.dayPnl, 2) : "--"}</span>
      <span className="num muted" style={{ fontSize: 9, textAlign: "right" }}>δ -0.50</span>
      <span style={{ fontSize: 9, color: "var(--color-text-muted)", paddingLeft: 8, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{pos.sector}</span>
    </div>
  );
}

function SparkCard({ ticker, label, labelColor, currentPrice, pct, entryPrice, closes, pnlSign, invertArrow }: {
  ticker: string; label: string; labelColor: string;
  currentPrice: number; pct: number; entryPrice: number;
  closes: number[]; pnlSign: number; invertArrow?: boolean;
}) {
  const chartData = closes.map((c, i) => ({ i, price: c }));
  const color = pnlSign >= 0 ? "#22C55E" : "#EF4444";
  return (
    <div style={{ borderBottom: "1px solid var(--color-border)", padding: "5px 10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 3 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span className="num" style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-primary)" }}>{ticker}</span>
          <span style={{ fontSize: 7, fontWeight: 600, color: labelColor }}>{label}</span>
        </div>
        <div style={{ textAlign: "right" }}>
          <span className="num" style={{ fontSize: 10, color: "var(--color-text-primary)" }}>{currentPrice > 0 ? fmtCurrency(currentPrice) : "--"}</span>
          {entryPrice > 0 && (
            <span className={`num ${signClass(pnlSign)}`} style={{ fontSize: 8, marginLeft: 5 }}>
              {pnlSign >= 0 ? "+" : ""}{fmtPct(pct)}
            </span>
          )}
        </div>
      </div>
      {chartData.length > 1 && (
        <div style={{ height: 28 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <Line type="monotone" dataKey="price" stroke={color} strokeWidth={1.2} dot={false} />
              {entryPrice > 0 && <ReferenceLine y={entryPrice} stroke="var(--color-text-muted)" strokeDasharray="2 2" strokeWidth={0.8} />}
              <YAxis domain={["auto", "auto"]} hide />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
