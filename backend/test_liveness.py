import datetime
import pandas as pd
import numpy as np
from app.market_liveness import MarketLivenessGuard, market_liveness


def test_crypto_classification():
    print("--- 1. Testing Crypto Asset Classification ---")
    assert MarketLivenessGuard.is_crypto_symbol("BTCUSD") is True
    assert MarketLivenessGuard.is_crypto_symbol("ETHUSD") is True
    assert MarketLivenessGuard.is_crypto_symbol("BTC/USDT") is True
    assert MarketLivenessGuard.is_crypto_symbol("SOLUSD.raw") is True
    assert MarketLivenessGuard.is_crypto_symbol("EURUSD") is False
    assert MarketLivenessGuard.is_crypto_symbol("XAUUSD") is False
    assert MarketLivenessGuard.is_crypto_symbol("US30") is False
    assert MarketLivenessGuard.is_crypto_symbol("NAS100") is False
    print("  [PASS] Crypto classification tests passed!")


def test_weekend_calendar_closure():
    print("--- 2. Testing Weekend Calendar Rules ---")
    # Saturday 12:00 UTC
    sat_dt = datetime.datetime(2026, 9, 19, 12, 0, tzinfo=datetime.timezone.utc)
    is_closed, reason = MarketLivenessGuard.is_weekend_closure_active("EURUSD", sat_dt)
    assert is_closed is True, f"EURUSD should be closed on Saturday: {reason}"
    print(f"  [PASS] EURUSD on Saturday: Closed ({reason})")

    # Sunday 14:00 UTC (before 21:00 UTC open)
    sun_dt = datetime.datetime(2026, 9, 20, 14, 0, tzinfo=datetime.timezone.utc)
    is_closed, reason = MarketLivenessGuard.is_weekend_closure_active("XAUUSD", sun_dt)
    assert is_closed is True, f"XAUUSD should be closed Sunday afternoon: {reason}"
    print(f"  [PASS] XAUUSD on Sunday 14:00 UTC: Closed ({reason})")

    # Monday 10:00 UTC
    mon_dt = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)
    is_closed, reason = MarketLivenessGuard.is_weekend_closure_active("EURUSD", mon_dt)
    assert is_closed is False, f"EURUSD should be open on Monday: {reason}"
    print("  [PASS] EURUSD on Monday 10:00 UTC: Open")

    # Crypto on Saturday (Crypto trades 24/7 on standard calendar)
    is_closed, reason = MarketLivenessGuard.is_weekend_closure_active("BTCUSD", sat_dt)
    assert is_closed is False, "BTCUSD should not be closed by weekend calendar guard"
    print("  [PASS] BTCUSD on Saturday: Not blocked by static weekend calendar (subject to live broker check)")


def test_candle_staleness_and_flatline():
    print("--- 3. Testing Candle Freshness & Flatline Detection ---")
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Test 3A: Fresh Candles
    recent_times = [now_utc - datetime.timedelta(minutes=15 * i) for i in range(10, 0, -1)]
    fresh_df = pd.DataFrame({
        "Time": recent_times,
        "Open": np.linspace(1.0800, 1.0850, 10),
        "High": np.linspace(1.0810, 1.0860, 10),
        "Low": np.linspace(1.0790, 1.0840, 10),
        "Close": np.linspace(1.0805, 1.0855, 10),
        "Volume": [1000] * 10
    })
    is_fresh, reason, age = MarketLivenessGuard.check_candle_freshness(fresh_df, "15m")
    assert is_fresh is True, f"Expected fresh candles to pass: {reason}"
    print("  [PASS] Fresh 15m candle stream: Verified Live")

    # Test 3B: Stale Candles (e.g. 2 days old)
    old_times = [now_utc - datetime.timedelta(days=2, hours=i) for i in range(10, 0, -1)]
    stale_df = pd.DataFrame({
        "Time": old_times,
        "Open": [1.0800] * 10,
        "High": [1.0820] * 10,
        "Low": [1.0780] * 10,
        "Close": [1.0810] * 10,
        "Volume": [1000] * 10
    })
    is_fresh, reason, age = MarketLivenessGuard.check_candle_freshness(stale_df, "1h")
    assert is_fresh is False, "Stale candles should be detected"
    print(f"  [PASS] Stale candle feed: Correctly rejected ({reason})")

    # Test 3C: Flatline / Zero Movement Candles
    flat_times = [now_utc - datetime.timedelta(minutes=5 * i) for i in range(5, 0, -1)]
    flat_df = pd.DataFrame({
        "Time": flat_times,
        "Open": [100.0] * 5,
        "High": [100.0] * 5,
        "Low": [100.0] * 5,
        "Close": [100.0] * 5,
        "Volume": [0] * 5
    })
    is_fresh, reason, age = MarketLivenessGuard.check_candle_freshness(flat_df, "5m")
    assert is_fresh is False, "Flatline candles should be detected"
    print(f"  [PASS] Zero-volatility flatline: Correctly rejected ({reason})")


def test_live_liveness_check():
    print("--- 4. Testing Unified Liveness Check with Current Market State ---")
    res_eur = market_liveness.check_liveness("EURUSD", "1h")
    print(f"  EURUSD (1h): is_open={res_eur.get('is_open')} | reason='{res_eur.get('reason')}' | source='{res_eur.get('source')}'")

    res_btc = market_liveness.check_liveness("BTCUSD", "1h")
    print(f"  BTCUSD (1h): is_open={res_btc.get('is_open')} | reason='{res_btc.get('reason')}' | source='{res_btc.get('source')}'")

    res_xau = market_liveness.check_liveness("XAUUSD", "1h")
    print(f"  XAUUSD (1h): is_open={res_xau.get('is_open')} | reason='{res_xau.get('reason')}' | source='{res_xau.get('source')}'")


if __name__ == "__main__":
    test_crypto_classification()
    test_weekend_calendar_closure()
    test_candle_staleness_and_flatline()
    test_live_liveness_check()
    print("\n>>> ALL MARKET LIVENESS & STAGNATION GUARD TESTS PASSED SUCCESSFULLY! <<<")
