import { fetcher } from "@/src/lib/fetcher";
import { AlertsPage } from "@/src/types/api";
import AlertsClient from "@/src/components/AlertsClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function AlertsPageRoute() {
  let initialPage: AlertsPage | null = null;
  try {
    initialPage = await fetcher<AlertsPage>("/v1/alerts?page=1&page_size=50");
  } catch {
    // Backend unavailable; render empty table
  }
  return (
    <ErrorBoundary>
      <AlertsClient initialPage={initialPage} />
    </ErrorBoundary>
  );
}
