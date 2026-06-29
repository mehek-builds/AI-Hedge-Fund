import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const tickers = req.nextUrl.searchParams.get("tickers") ?? "";
  if (!tickers) return NextResponse.json({});

  const symbols = tickers.split(",").map(s => s.trim()).filter(Boolean);
  const result: Record<string, {
    price: number;
    change: number;
    changePct: number;
    prevClose: number;
    closes: number[];
    dates: string[];
  }> = {};

  await Promise.all(
    symbols.map(async (sym) => {
      try {
        const url = `https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=1d&range=10d`;
        const res = await fetch(url, {
          headers: { "User-Agent": "Mozilla/5.0" },
          next: { revalidate: 60 },
        });
        if (!res.ok) return;
        const data = await res.json();
        const chartResult = data?.chart?.result?.[0];
        if (!chartResult) return;

        const meta = chartResult.meta;
        const price: number = meta.regularMarketPrice ?? meta.previousClose;
        const prevClose: number = meta.chartPreviousClose ?? meta.previousClose;
        const change = price - prevClose;
        const changePct = prevClose ? (change / prevClose) * 100 : 0;

        const timestamps: number[] = chartResult.timestamp ?? [];
        const closePrices: number[] = chartResult.indicators?.quote?.[0]?.close ?? [];
        const closes = closePrices.filter((c: number | null) => c != null) as number[];
        const dates = timestamps.slice(-closes.length).map((ts: number) => {
          const d = new Date(ts * 1000);
          return `${d.getMonth() + 1}/${d.getDate()}`;
        });

        result[sym] = { price, change, changePct, prevClose, closes, dates };
      } catch {
        // skip failed tickers
      }
    })
  );

  return NextResponse.json(result, {
    headers: { "Cache-Control": "no-store" },
  });
}
