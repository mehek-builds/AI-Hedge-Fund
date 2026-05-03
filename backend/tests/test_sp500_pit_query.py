from datetime import date, datetime
import pytest
from sqlalchemy import insert

from app.models.sp500_constituents import SP500Constituent
from app.queries.sp500_membership import sp500_members_as_of


@pytest.mark.asyncio
async def test_survivorship_bias_pit_query(db_session):
    """Ticker FOO: in S&P 2020-01-01 to 2022-06-01.

    Assertions:
      - members_as_of(2019-01-01) does NOT contain FOO
      - members_as_of(2021-01-01) DOES contain FOO
      - members_as_of(2023-01-01) does NOT contain FOO
    And SURV (still active since 2010) appears at all three dates.
    """
    await db_session.execute(insert(SP500Constituent).values([
        {"symbol": "SURV", "company_name": "Survivor Co",
         "added_date": date(2010, 1, 1), "removed_date": None},
        {"symbol": "FOO",  "company_name": "Foo Co",
         "added_date": date(2020, 1, 1), "removed_date": date(2022, 6, 1)},
    ]))
    await db_session.commit()

    m_2019 = await sp500_members_as_of(db_session, date(2019, 1, 1))
    m_2021 = await sp500_members_as_of(db_session, date(2021, 1, 1))
    m_2023 = await sp500_members_as_of(db_session, date(2023, 1, 1))

    assert "FOO" not in m_2019
    assert "FOO" in m_2021
    assert "FOO" not in m_2023
    assert all("SURV" in m for m in (m_2019, m_2021, m_2023))


@pytest.mark.asyncio
async def test_pit_query_handles_re_added_ticker(db_session):
    """A ticker removed and later re-added has two rows."""
    await db_session.execute(insert(SP500Constituent).values([
        {"symbol": "ZZ", "added_date": date(2015, 1, 1), "removed_date": date(2018, 1, 1)},
        {"symbol": "ZZ", "added_date": date(2021, 1, 1), "removed_date": None},
    ]))
    await db_session.commit()

    assert "ZZ" in await sp500_members_as_of(db_session, date(2016, 6, 1))
    assert "ZZ" not in await sp500_members_as_of(db_session, date(2019, 6, 1))
    assert "ZZ" in await sp500_members_as_of(db_session, date(2022, 6, 1))
