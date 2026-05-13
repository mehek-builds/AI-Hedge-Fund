import { fetcher } from "@/src/lib/fetcher";
import { Position } from "@/src/types/api";
import PositionsClient from "@/src/components/PositionsClient";
import ErrorBoundary from "@/src/components/ErrorBoundary";

export default async function PositionsPage() {
  let positions: Position[] = [];
  try {
    positions = await fetcher<Position[]>("/api/v1/positions");
  } catch {
    /* empty */
  }
  return (
    <ErrorBoundary>
      <PositionsClient initialPositions={positions} />
    </ErrorBoundary>
  );
}
