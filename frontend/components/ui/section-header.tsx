/** Amber uppercase section header with optional right-side count/label. */
export function SectionHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      padding: "5px 10px 4px",
      borderBottom: "1px solid var(--color-border)",
      gap: 6,
    }}>
      <span style={{
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: "var(--color-amber)",
      }}>
        {title}
      </span>
      {right && (
        <span style={{
          marginLeft: "auto",
          fontSize: 9,
          fontFamily: "var(--font-family-mono)",
          color: "var(--color-text-muted)",
        }}>
          {right}
        </span>
      )}
    </div>
  );
}
