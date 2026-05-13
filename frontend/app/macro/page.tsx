import { fetcher } from "@/src/lib/fetcher";
import { MacroDataEnriched } from "@/src/types/api";
import MacroClient from "@/src/components/MacroClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function MacroPage() {
  let data: MacroDataEnriched | null = null;
  try {
    data = await fetcher<MacroDataEnriched>("/api/v1/macro");
  } catch {
    /* empty */
  }
  return (
    <ErrorBoundary>
      <MacroClient initialData={data} />
    </ErrorBoundary>
  );
}
