import { fetcher } from "@/src/lib/fetcher";
import { SettingsData } from "@/src/types/api";
import SettingsClient from "@/src/components/SettingsClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function SettingsPage() {
  let settings: SettingsData | null = null;
  try {
    settings = await fetcher<SettingsData>("/api/v1/settings");
  } catch {
    /* SettingsClient handles null */
  }
  return (
    <ErrorBoundary>
      <SettingsClient initialSettings={settings} />
    </ErrorBoundary>
  );
}
