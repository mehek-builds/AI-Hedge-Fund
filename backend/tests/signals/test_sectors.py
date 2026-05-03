"""Unit tests for the GICS sector map, forward P/E table, and hurdle rates."""
from decimal import Decimal

import pytest


def test_sector_for_aapl_returns_tech():
    from app.signals.sectors import sector_for
    assert sector_for("AAPL") == "Tech"


def test_sector_for_xom_returns_energy():
    from app.signals.sectors import sector_for
    assert sector_for("XOM") == "Energy"


def test_sector_for_jpm_returns_financials():
    from app.signals.sectors import sector_for
    assert sector_for("JPM") == "Financials"


def test_sector_for_unh_returns_healthcare():
    from app.signals.sectors import sector_for
    assert sector_for("UNH") == "Healthcare"


def test_sector_for_pg_returns_consumer():
    from app.signals.sectors import sector_for
    assert sector_for("PG") == "Consumer"


def test_sector_for_cat_returns_industrials():
    from app.signals.sectors import sector_for
    assert sector_for("CAT") == "Industrials"


def test_sector_for_nee_returns_utilities():
    from app.signals.sectors import sector_for
    assert sector_for("NEE") == "Utilities"


def test_sector_for_unknown_returns_other():
    from app.signals.sectors import sector_for
    assert sector_for("ZZZZ") == "Other"


def test_sector_for_lowercase_input():
    from app.signals.sectors import sector_for
    assert sector_for("aapl") == "Tech"


def test_sector_for_empty_string_returns_other():
    from app.signals.sectors import sector_for
    assert sector_for("") == "Other"


def test_sector_for_none_returns_other():
    from app.signals.sectors import sector_for
    assert sector_for(None) == "Other"


def test_sector_fwd_pe_tech():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Tech"] == Decimal("28.0")


def test_sector_fwd_pe_healthcare():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Healthcare"] == Decimal("18.0")


def test_sector_fwd_pe_financials():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Financials"] == Decimal("13.0")


def test_sector_fwd_pe_consumer():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Consumer"] == Decimal("22.0")


def test_sector_fwd_pe_energy():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Energy"] == Decimal("12.0")


def test_sector_fwd_pe_industrials():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Industrials"] == Decimal("19.0")


def test_sector_fwd_pe_utilities():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Utilities"] == Decimal("16.0")


def test_sector_fwd_pe_other():
    from app.signals.sectors import SECTOR_FWD_PE
    assert SECTOR_FWD_PE["Other"] == Decimal("18.0")


def test_sector_hurdle_tech():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Tech"] == 60


def test_sector_hurdle_healthcare():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Healthcare"] == 55


def test_sector_hurdle_financials():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Financials"] == 50


def test_sector_hurdle_consumer():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Consumer"] == 45


def test_sector_hurdle_energy():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Energy"] == 45


def test_sector_hurdle_industrials():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Industrials"] == 45


def test_sector_hurdle_utilities():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Utilities"] == 45


def test_sector_hurdle_other():
    from app.signals.sectors import SECTOR_HURDLE
    assert SECTOR_HURDLE["Other"] == 45


def test_all_sectors_in_fwd_pe():
    from app.signals.sectors import SECTORS, SECTOR_FWD_PE
    for s in SECTORS:
        assert s in SECTOR_FWD_PE, f"Sector {s} missing from SECTOR_FWD_PE"


def test_all_sectors_in_hurdle():
    from app.signals.sectors import SECTORS, SECTOR_HURDLE
    for s in SECTORS:
        assert s in SECTOR_HURDLE, f"Sector {s} missing from SECTOR_HURDLE"


def test_all_fwd_pe_values_are_decimal():
    from app.signals.sectors import SECTOR_FWD_PE
    for sector, value in SECTOR_FWD_PE.items():
        assert isinstance(value, Decimal), f"SECTOR_FWD_PE[{sector}] is not a Decimal"
