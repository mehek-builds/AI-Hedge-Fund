import { fetcher } from "@/src/lib/fetcher";
import { RLStateData } from "@/src/types/api";
import RLConsoleClient from "@/src/components/RLConsoleClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function RLConsolePage() {
  let data: RLStateData | null = null;
  try {
    data = await fetcher<RLStateData>("/v1/rl/state");
  } catch {
    // Stub endpoint may not be running; render with empty state
  }
  return (
    <ErrorBoundary>
      <RLConsoleClient initialData={data} />
    </ErrorBoundary>
  );
}
