"use client";

import React, { useState, useCallback } from "react";
import PageHeader from "@/src/components/PageHeader";
import LoadingSpinner from "@/src/components/LoadingSpinner";
import { SettingsData, SettingsDataPatch } from "@/src/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_SETTINGS: SettingsData = {
  ENABLE_SHORT_SIDE: false,
  STOP_LOSS_PCT: 0.02,
  TAKE_PROFIT_PCT: 0.04,
  max_alerts_per_hour: 10,
};

interface Props {
  initialSettings: SettingsData | null;
}

export default function SettingsClient({ initialSettings }: Props) {
  const init = initialSettings ?? DEFAULT_SETTINGS;

  const [values, setValues] = useState<SettingsData>(init);
  const [savedValues, setSavedValues] = useState<SettingsData>(init);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [saveError, setSaveError] = useState("");
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveStatus("idle");

    // Build patch with only changed fields
    const patch: SettingsDataPatch = {};
    if (values.ENABLE_SHORT_SIDE !== savedValues.ENABLE_SHORT_SIDE) {
      patch.ENABLE_SHORT_SIDE = values.ENABLE_SHORT_SIDE;
    }
    if (values.STOP_LOSS_PCT !== savedValues.STOP_LOSS_PCT) {
      patch.STOP_LOSS_PCT = values.STOP_LOSS_PCT;
    }
    if (values.TAKE_PROFIT_PCT !== savedValues.TAKE_PROFIT_PCT) {
      patch.TAKE_PROFIT_PCT = values.TAKE_PROFIT_PCT;
    }
    if (values.max_alerts_per_hour !== savedValues.max_alerts_per_hour) {
      patch.max_alerts_per_hour = values.max_alerts_per_hour;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });

      if (res.ok) {
        const updated: SettingsData = await res.json();
        setSavedValues(updated);
        setValues(updated);
        setSaveStatus("success");
        setSaving(false);
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else {
        setValues(savedValues);
        setSaveError("Settings could not be saved. The value may be out of the allowed range.");
        setSaveStatus("error");
        setSaving(false);
      }
    } catch {
      setValues(savedValues);
      setSaveError("Settings could not be saved. Network error.");
      setSaveStatus("error");
      setSaving(false);
    }
  }, [values, savedValues]);

  const handleReset = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/settings/reset`, {
        method: "POST",
      });
      if (res.ok) {
        const updated: SettingsData = await res.json();
        setValues(updated);
        setSavedValues(updated);
        setShowResetConfirm(false);
      }
    } catch {
      setShowResetConfirm(false);
    }
  }, []);

  const inputStyle: React.CSSProperties = {
    backgroundColor: "#0F2040",
    border: "1px solid #2471A3",
    color: "white",
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: "14px",
    borderRadius: "6px",
    padding: "8px 12px",
    width: "120px",
    outline: "none",
  };

  const sectionHeaderStyle: React.CSSProperties = {
    fontSize: "16px",
    fontWeight: 600,
    color: "white",
    marginBottom: "16px",
    paddingBottom: "8px",
    borderBottom: "1px solid #1A3050",
  };

  const fieldRowStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "16px 0",
    borderBottom: "1px solid #1A3050",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: "14px",
    color: "white",
    fontFamily: "Inter, system-ui, sans-serif",
    marginBottom: "4px",
  };

  const subLabelStyle: React.CSSProperties = {
    fontSize: "12px",
    color: "#6B8EAD",
    fontFamily: "Inter, system-ui, sans-serif",
  };

  const isOn = values.ENABLE_SHORT_SIDE;

  return (
    <div>
      <PageHeader title="Settings" />

      <div style={{ padding: "32px", maxWidth: "640px" }}>
        {/* Info banner */}
        <div
          style={{
            fontSize: "14px",
            color: "#6B8EAD",
            fontFamily: "Inter, system-ui, sans-serif",
            marginBottom: "24px",
          }}
        >
          Settings loaded from environment. Changes here override runtime values without restart.
        </div>

        {/* Trading Controls section */}
        <div style={{ marginBottom: "32px" }}>
          <div style={sectionHeaderStyle}>Trading Controls</div>

          {/* ENABLE_SHORT_SIDE toggle */}
          <div style={fieldRowStyle}>
            <div>
              <div style={labelStyle}>Enable Short Side</div>
              <div style={subLabelStyle}>Allow the system to submit short orders via Alpaca.</div>
            </div>
            <div
              role="switch"
              aria-checked={isOn}
              tabIndex={0}
              onClick={() => setValues((v) => ({ ...v, ENABLE_SHORT_SIDE: !v.ENABLE_SHORT_SIDE }))}
              onKeyDown={(e) => {
                if (e.key === " " || e.key === "Enter") {
                  setValues((v) => ({ ...v, ENABLE_SHORT_SIDE: !v.ENABLE_SHORT_SIDE }));
                }
              }}
              style={{
                position: "relative",
                width: "48px",
                height: "28px",
                borderRadius: "14px",
                cursor: "pointer",
                backgroundColor: isOn ? "#2471A3" : "#1A3050",
                transition: "background-color 150ms ease-in-out",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  top: "3px",
                  left: isOn ? "23px" : "3px",
                  width: "22px",
                  height: "22px",
                  borderRadius: "11px",
                  backgroundColor: isOn ? "#FFFFFF" : "#6B8EAD",
                  transition: "left 150ms ease-in-out, background-color 150ms ease-in-out",
                }}
              />
            </div>
          </div>

          {/* STOP_LOSS_PCT */}
          <div style={fieldRowStyle}>
            <div>
              <div style={labelStyle}>Stop Loss %</div>
              <div style={subLabelStyle}>
                Percentage below entry to trigger stop. Default: 2.0%
              </div>
            </div>
            <input
              type="number"
              step="0.001"
              min="0.001"
              max="50"
              value={(values.STOP_LOSS_PCT * 100).toFixed(2)}
              onChange={(e) =>
                setValues((v) => ({
                  ...v,
                  STOP_LOSS_PCT: parseFloat(e.target.value) / 100,
                }))
              }
              style={inputStyle}
            />
          </div>

          {/* TAKE_PROFIT_PCT */}
          <div style={fieldRowStyle}>
            <div>
              <div style={labelStyle}>Take Profit %</div>
              <div style={subLabelStyle}>
                Percentage above entry to trigger take profit. Default: 4.0%
              </div>
            </div>
            <input
              type="number"
              step="0.001"
              min="0.001"
              max="100"
              value={(values.TAKE_PROFIT_PCT * 100).toFixed(2)}
              onChange={(e) =>
                setValues((v) => ({
                  ...v,
                  TAKE_PROFIT_PCT: parseFloat(e.target.value) / 100,
                }))
              }
              style={inputStyle}
            />
          </div>
        </div>

        {/* Alert Thresholds section */}
        <div style={{ marginBottom: "32px" }}>
          <div style={sectionHeaderStyle}>Alert Thresholds</div>

          {/* max_alerts_per_hour */}
          <div style={fieldRowStyle}>
            <div>
              <div style={labelStyle}>Max Alerts / Hour</div>
              <div style={subLabelStyle}>
                Maximum alerts delivered per event type per hour.
              </div>
            </div>
            <input
              type="number"
              step="1"
              min="1"
              max="100"
              value={values.max_alerts_per_hour}
              onChange={(e) =>
                setValues((v) => ({
                  ...v,
                  max_alerts_per_hour: parseInt(e.target.value, 10),
                }))
              }
              style={inputStyle}
            />
          </div>
        </div>

        {/* Form footer */}
        <div
          style={{
            marginTop: "32px",
            display: "flex",
            gap: "12px",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          {/* Save button */}
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              backgroundColor: "#2471A3",
              color: "white",
              fontFamily: "Inter, system-ui, sans-serif",
              fontSize: "14px",
              fontWeight: 500,
              padding: "10px 24px",
              borderRadius: "6px",
              border: "none",
              cursor: saving ? "not-allowed" : "pointer",
              opacity: saving ? 0.7 : 1,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {saving ? (
              <>
                <LoadingSpinner /> Saving...
              </>
            ) : (
              "Save Settings"
            )}
          </button>

          {/* Reset to Defaults button */}
          <button
            onClick={() => setShowResetConfirm(true)}
            style={{
              backgroundColor: "transparent",
              border: "1px solid #E74C3C",
              color: "#E74C3C",
              fontFamily: "Inter, system-ui, sans-serif",
              fontSize: "13px",
              padding: "10px 20px",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Reset to Defaults
          </button>
        </div>

        {/* Inline feedback */}
        {saveStatus === "success" && (
          <div
            style={{
              marginTop: "8px",
              fontSize: "13px",
              color: "#27AE60",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            Settings saved.
          </div>
        )}
        {saveStatus === "error" && (
          <div
            style={{
              marginTop: "8px",
              fontSize: "13px",
              color: "#E74C3C",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {saveError}
          </div>
        )}

        {/* Inline destructive confirm */}
        {showResetConfirm && (
          <div
            style={{
              marginTop: "8px",
              backgroundColor: "#0F2040",
              border: "1px solid #E74C3C",
              borderRadius: "6px",
              padding: "16px",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                color: "white",
                fontFamily: "Inter, system-ui, sans-serif",
              }}
            >
              This will revert to environment defaults. Confirm?
            </span>
            <div style={{ marginTop: "12px", display: "flex", gap: "16px" }}>
              <button
                onClick={handleReset}
                style={{
                  color: "#E74C3C",
                  backgroundColor: "transparent",
                  border: "none",
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontSize: "13px",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                Yes, reset
              </button>
              <button
                onClick={() => setShowResetConfirm(false)}
                style={{
                  color: "#6B8EAD",
                  backgroundColor: "transparent",
                  border: "none",
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontSize: "13px",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
