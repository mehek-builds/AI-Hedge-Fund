import { fetcher } from "@/src/lib/fetcher";
import { DashboardData } from "@/src/types/api";
import DashboardClient from "@/src/components/DashboardClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";
import SkeletonRect from "@/src/components/SkeletonRect";
import { Suspense } from "react";

export default async function DashboardPage() {
  let data: DashboardData | null = null;
  try {
    data = await fetcher<DashboardData>("/api/v1/dashboard");
  } catch {
    // DashboardClient will show empty/error state
  }

  return (
    <ErrorBoundary>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardClient initialData={data} />
      </Suspense>
    </ErrorBoundary>
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ padding: "32px 32px" }}>
      <div style={{ marginBottom: "32px" }}>
        <SkeletonRect width="200px" height={28} borderRadius={4} />
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr",
          gap: "24px",
          marginBottom: "32px",
        }}
      >
        {[0, 1, 2, 3].map((i) => (
          <SkeletonRect key={i} width="100%" height={120} borderRadius={8} />
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "1px" }}>
        {[0, 1, 2, 3, 4].map((i) => (
          <SkeletonRect key={i} width="100%" height={44} borderRadius={0} />
        ))}
      </div>
    </div>
  );
}
