"""Ken French Five-Factor (FF5) data loader.

Downloads MKT-RF, SMB, HML, RMW, CMA from the French data library.
Falls back to synthetic data when network is unavailable.
"""

from __future__ import annotations

import io
import zipfile
import requests
import pandas as pd
import numpy as np
from loguru import logger


_FF5_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_CSV.zip"
)

_FACTOR_COLS = ["MKT-RF", "SMB", "HML", "RMW", "CMA", "RF"]


class FactorDataClient:
    """Loads Fama-French Five-Factor monthly returns."""

    def __init__(self):
        self._cache: pd.DataFrame | None = None

    def get_factors(self, start: str = "2005-01-01") -> pd.DataFrame:
        """Return monthly FF5 factor returns (decimal, not percent)."""
        if self._cache is None:
            self._cache = self._download()

        df = self._cache.copy()
        df.index = pd.to_datetime(df.index, format="%Y%m")
        df = df[df.index >= pd.Timestamp(start)]
        return df

    def get_factor_slice(
        self, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        df = self.get_factors(start=str(start.date()))
        return df[(df.index >= start) & (df.index <= end)]

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _download(self) -> pd.DataFrame:
        try:
            resp = requests.get(_FF5_URL, timeout=15)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                csv_name = [n for n in z.namelist() if n.endswith(".CSV") or n.endswith(".csv")][0]
                with z.open(csv_name) as f:
                    raw = f.read().decode("latin-1")
            df = self._parse_french_csv(raw)
            logger.info(f"FF5 data loaded: {len(df)} months")
            return df
        except Exception as exc:
            logger.warning(f"FF5 download failed: {exc} — using synthetic")
            return self._synthetic()

    @staticmethod
    def _parse_french_csv(raw: str) -> pd.DataFrame:
        lines = raw.splitlines()
        # Find the header row (contains "Mkt-RF")
        header_idx = next(
            i for i, l in enumerate(lines) if "Mkt-RF" in l or "MKT-RF" in l.upper()
        )
        # Find the annual section break (empty line or "Annual Factors")
        data_lines = []
        for line in lines[header_idx + 1 :]:
            stripped = line.strip()
            if not stripped or "Annual" in stripped:
                break
            data_lines.append(stripped)

        df = pd.read_csv(
            io.StringIO("\n".join(data_lines)),
            header=None,
            names=["date", "MKT-RF", "SMB", "HML", "RMW", "CMA", "RF"],
        )
        df = df[df["date"].astype(str).str.match(r"^\d{6}$")]
        df = df.set_index("date")
        df = df.apply(pd.to_numeric, errors="coerce") / 100  # percent → decimal
        return df.dropna()

    @staticmethod
    def _synthetic() -> pd.DataFrame:
        dates = pd.period_range("2000-01", "2024-12", freq="M")
        rng = np.random.default_rng(42)
        n = len(dates)
        data = {
            "MKT-RF": rng.normal(0.007, 0.045, n),
            "SMB":    rng.normal(0.002, 0.030, n),
            "HML":    rng.normal(-0.001, 0.030, n),
            "RMW":    rng.normal(0.003, 0.020, n),
            "CMA":    rng.normal(0.002, 0.018, n),
            "RF":     rng.uniform(0.0001, 0.0025, n),
        }
        df = pd.DataFrame(data, index=dates.astype(str))
        return df
