/** Macro gate regime badge. */
export function GateBadge({ regime }: { regime: string }) {
  const color =
    regime === "Expansion" ? "var(--color-positive)" :
    regime === "Caution"   ? "var(--color-warning)"  :
    regime === "Crisis"    ? "var(--color-negative)"  : "var(--color-text-muted)";
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      padding: "2px 8px",
      borderRadius: 3,
      fontSize: 10,
      fontWeight: 500,
      letterSpacing: "0.04em",
      color,
      background: `color-mix(in srgb, ${color} 12%, transparent)`,
    }}>
      {regime}
    </span>
  );
}
