"use client";
import { useQuery, useMutation, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { api, Setting } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtDatetime } from "@/lib/format";

const qc = new QueryClient();
export default function SettingsPage() {
  return <QueryClientProvider client={qc}><Settings /></QueryClientProvider>;
}

const FLAG_DESCRIPTIONS: Record<string, string> = {
  ENABLE_SHORT_SIDE: "Allow RL agent to open short positions. Affects live order routing.",
  MAX_POSITION_PCT: "Max single-name allocation as % of NAV (default 0.05).",
  MAG7_CAP_PCT: "Max combined Mag-7 allocation as % of NAV (default 0.12).",
  MIN_SIGNAL_THRESHOLD: "Minimum signal composite to enter a position (default 1.0).",
  MIN_QUALITY_SCORE: "Minimum earnings quality score to enter (default 0.65).",
  SLIPPAGE_BPS: "Assumed execution slippage in basis points (default 12.5).",
  MACRO_HALT_OVERRIDE: "Bypass macro halt gate (use with caution).",
};

function Settings() {
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });

  const update = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => api.updateSetting(key, value),
    onSuccess: () => { refetch(); showToast("Saved", true); },
    onError: () => showToast("Failed to save", false),
  });

  function showToast(msg: string, ok: boolean) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  }

  const boolFlags = data.filter(s => ["true","false"].includes(s.value.toLowerCase()));
  const numericSettings = data.filter(s => !["true","false"].includes(s.value.toLowerCase()));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="Settings" right={`${data.length} keys`} />

      {toast && (
        <div style={{
          position: "fixed", bottom: 40, right: 20, zIndex: 100,
          padding: "8px 16px", borderRadius: 4,
          background: toast.ok ? "var(--color-positive)" : "var(--color-negative)",
          color: "#fff", fontSize: 12, fontWeight: 500,
        }}>{toast.msg}</div>
      )}

      {isLoading && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading...</div>}

      {/* Feature flags */}
      {boolFlags.length > 0 && (
        <>
          <SectionHeader title="Feature flags" />
          {boolFlags.map(s => (
            <FlagRow key={s.key} setting={s} onToggle={(val) => {
              if (s.key === "ENABLE_SHORT_SIDE" && val === "true") {
                if (!window.confirm("This affects live order routing. Continue?")) return;
              }
              update.mutate({ key: s.key, value: val });
            }} />
          ))}
        </>
      )}

      {/* Numeric settings */}
      {numericSettings.length > 0 && (
        <>
          <SectionHeader title="Thresholds and parameters" />
          {numericSettings.map(s => (
            <NumericRow key={s.key} setting={s} onSave={(val) => update.mutate({ key: s.key, value: val })} />
          ))}
        </>
      )}

      {!isLoading && data.length === 0 && (
        <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>
          No settings found. Settings are populated on first boot.
        </div>
      )}
    </div>
  );
}

function FlagRow({ setting, onToggle }: { setting: Setting; onToggle: (v: string) => void }) {
  const isOn = setting.value.toLowerCase() === "true";
  const desc = FLAG_DESCRIPTIONS[setting.key];
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--color-border)", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontFamily: "var(--font-family-mono)", color: "var(--color-text-primary)", marginBottom: 2 }}>{setting.key}</div>
        {desc && <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{desc}</div>}
        <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2 }}>Updated {fmtDatetime(setting.updated_at)}</div>
      </div>
      <button
        onClick={() => onToggle(isOn ? "false" : "true")}
        style={{
          width: 44, height: 22, borderRadius: 11, border: "none", cursor: "pointer",
          background: isOn ? "var(--color-positive)" : "var(--color-border-strong)",
          position: "relative", flexShrink: 0, transition: "background 0.15s",
        }}
      >
        <div style={{
          position: "absolute", top: 3, left: isOn ? 24 : 3,
          width: 16, height: 16, borderRadius: "50%", background: "#fff",
          transition: "left 0.15s",
        }} />
      </button>
    </div>
  );
}

function NumericRow({ setting, onSave }: { setting: Setting; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(setting.value);
  const desc = FLAG_DESCRIPTIONS[setting.key];
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--color-border)", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontFamily: "var(--font-family-mono)", color: "var(--color-text-primary)", marginBottom: 2 }}>{setting.key}</div>
        {desc && <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{desc}</div>}
        <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2 }}>Updated {fmtDatetime(setting.updated_at)}</div>
      </div>
      {editing ? (
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input
            value={val}
            onChange={e => setVal(e.target.value)}
            autoFocus
            style={{ padding: "4px 8px", background: "var(--color-bg-panel)", border: "1px solid var(--color-border-strong)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 12, fontFamily: "var(--font-family-mono)", width: 100 }}
          />
          <button onClick={() => { onSave(val); setEditing(false); }} style={{ padding: "3px 10px", borderRadius: 3, border: "none", background: "var(--color-accent)", color: "#fff", fontSize: 10, cursor: "pointer", fontWeight: 500 }}>Save</button>
          <button onClick={() => { setVal(setting.value); setEditing(false); }} style={{ padding: "3px 8px", borderRadius: 3, border: "1px solid var(--color-border)", background: "none", color: "var(--color-text-muted)", fontSize: 10, cursor: "pointer" }}>Cancel</button>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="num" style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-primary)" }}>{setting.value}</span>
          <button onClick={() => setEditing(true)} style={{ padding: "3px 8px", borderRadius: 3, border: "1px solid var(--color-border)", background: "none", color: "var(--color-text-muted)", fontSize: 10, cursor: "pointer" }}>Edit</button>
        </div>
      )}
    </div>
  );
}
