/** INTACT / MONITOR / BROKEN badge. */
export function ThesisBadge({ status }: { status: string | null }) {
  const s = (status ?? "").toUpperCase();
  const color =
    s === "INTACT"  ? "var(--color-positive)" :
    s === "MONITOR" ? "var(--color-warning)"  :
    s === "BROKEN"  ? "var(--color-negative)" : "var(--color-text-muted)";
  const bg = color.replace(")", ", 0.12)").replace("var(", "color-mix(in srgb, var(");

  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      padding: "1px 5px",
      borderRadius: 2,
      fontSize: 8,
      fontWeight: 600,
      letterSpacing: "0.05em",
      textTransform: "uppercase",
      color,
      background: `color-mix(in srgb, ${color} 15%, transparent)`,
      border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
    }}>
      {s || "—"}
    </span>
  );
}
