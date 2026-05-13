import { fetcher } from "@/src/lib/fetcher";
import { BacktestRunSummary } from "@/src/types/api";
import BacktestClient from "@/src/components/BacktestClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function BacktestPage() {
  let runs: BacktestRunSummary[] = [];
  try {
    runs = await fetcher<BacktestRunSummary[]>("/v1/backtest/runs");
  } catch {
    // Backend may not be reachable; render empty state
  }
  return (
    <ErrorBoundary>
      <BacktestClient initialRuns={runs} />
    </ErrorBoundary>
  );
}
