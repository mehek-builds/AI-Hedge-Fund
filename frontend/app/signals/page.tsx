import { fetcher } from "@/src/lib/fetcher";
import { SignalRow } from "@/src/types/api";
import SignalFeedClient from "@/src/components/SignalFeedClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function SignalFeedPage() {
  let signals: SignalRow[] = [];
  try {
    signals = await fetcher<SignalRow[]>("/api/v1/signals/recent?limit=20");
  } catch {
    /* empty */
  }
  return (
    <ErrorBoundary>
      <SignalFeedClient initialSignals={signals} />
    </ErrorBoundary>
  );
}
