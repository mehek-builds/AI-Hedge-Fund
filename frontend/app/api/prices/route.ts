import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const tickers = req.nextUrl.searchParams.get("tickers") ?? "";
  if (!tickers) return NextResponse.json({});

  const symbols = tickers.split(",").map(s => s.trim()).filter(Boolean);
  const result: Record<string, {
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
  }> = {};

  await Promise.all(
    symbols.map(async (sym) => {
      try {
        // Fetch daily data for historical closes
        const dayUrl = `https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=1d&range=10d`;
        const [dayRes, intradayRes] = await Promise.all([
          fetch(dayUrl, { headers: { "User-Agent": "Mozilla/5.0" }, next: { revalidate: 60 } }),
          fetch(
            `https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=5m&range=1d`,
            { headers: { "User-Agent": "Mozilla/5.0" }, next: { revalidate: 30 } }
          ),
        ]);

        if (!dayRes.ok) return;
        const dayData = await dayRes.json();
        const dayResult = dayData?.chart?.result?.[0];
        if (!dayResult) return;

        const meta = dayResult.meta;
        const price: number = meta.regularMarketPrice ?? meta.previousClose;
        const open: number = meta.regularMarketOpen ?? price;
        const prevClose: number = meta.chartPreviousClose ?? meta.previousClose;

        // 10-day history for NAV chart
        const timestamps: number[] = dayResult.timestamp ?? [];
        const closePrices: number[] = dayResult.indicators?.quote?.[0]?.close ?? [];
        const closes = closePrices.filter((c: number | null) => c != null) as number[];
        const dates = timestamps.slice(-closes.length).map((ts: number) => {
          const d = new Date(ts * 1000);
          return `${d.getMonth() + 1}/${d.getDate()}`;
        });

        // Intraday 5m data — find price from ~1 hour ago
        let price1hAgo = open;
        const intradayTimestamps: number[] = [];
        const intradayPrices: number[] = [];

        if (intradayRes.ok) {
          const intradayData = await intradayRes.json();
          const intra = intradayData?.chart?.result?.[0];
          if (intra) {
            const iTs: number[] = intra.timestamp ?? [];
            const iClose: (number | null)[] = intra.indicators?.quote?.[0]?.close ?? [];
            const nowMs = Date.now();
            const oneHourAgoMs = nowMs - 60 * 60 * 1000;

            iTs.forEach((ts, i) => {
              const c = iClose[i];
              if (c == null) return;
              intradayTimestamps.push(ts);
              intradayPrices.push(c);
              // Price closest to 1 hour ago
              if (ts * 1000 <= oneHourAgoMs) {
                price1hAgo = c;
              }
            });
          }
        }

        const change1h = price - price1hAgo;
        const changePct1h = price1hAgo ? (change1h / price1hAgo) * 100 : 0;
        const change = price - prevClose;
        const changePct = prevClose ? (change / prevClose) * 100 : 0;

        result[sym] = {
          price, open, prevClose, price1hAgo,
          change, changePct,
          change1h, changePct1h,
          closes, dates,
          intradayTimestamps, intradayPrices,
        };
      } catch {
        // skip failed tickers
      }
    })
  );

  return NextResponse.json(result, {
    headers: { "Cache-Control": "no-store" },
  });
}
