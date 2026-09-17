import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.data_fetcher import MarketDataFetcher, get_current_session_info
from app.forecasting.chronos_engine import ai_engine, DEVICE
from app.forecasting.signal_generator import signal_generator
from app.config import config_manager


def test_full_pipeline():
    print(f"=== Testing Pipeline on {DEVICE} ===")
    
    # 1. Test Session Detector
    session_info = get_current_session_info()
    print(f"Session Info: {session_info}")

    # 2. Test Fetching 500 candles for Gold and Bitcoin
    test_symbols = [
        {"symbol": "GC=F", "name": "Gold Futures", "category": "Gold", "est_spread_pct": 0.015},
        {"symbol": "BTC-USD", "name": "Bitcoin", "category": "Crypto", "est_spread_pct": 0.02}
    ]

    for asset in test_symbols:
        sym = asset["symbol"]
        print(f"\n--- Testing {sym} ({asset['name']}) ---")
        df, err = MarketDataFetcher.fetch_candles(sym, interval="1h", target_count=500)
        if err:
            print(f"Error fetching {sym}: {err}")
            continue
        print(f"Fetched {len(df)} candles. Latest Close: {df['Close'].iloc[-1]:.2f}")

        # 3. Test 5-candle AI forecast
        forecast = ai_engine.forecast_next_5(df, interval="1h", prediction_length=5)
        print(f"Model used: {forecast['model_used']}")
        print(f"Direction: {forecast['direction']}, Expected Return: {forecast['expected_return_pct']}%")
        print(f"Predicted 5 Candles:")
        for idx, c in enumerate(forecast['predicted_candles']):
            print(f"  Step {idx+1}: Close={c['close']}, p10={c['p10']}, p90={c['p90']}")

        # 4. Test Signal Evaluator (Spread < 5% SL rule)
        strat_cfg = config_manager.get("strategy", {})
        signal = signal_generator.evaluate_signal(forecast, df, asset, strat_cfg)
        if signal:
            print(f"Signal Evaluation:")
            print(f"  Entry: {signal['entry_price']}, SL: {signal['stop_loss']}, TP1: {signal['take_profit_1']}")
            print(f"  Risk/Reward: {signal['risk_reward_ratio']}")
            print(f"  Spread-to-SL Ratio: {signal['spread_to_sl_ratio_pct']}% (Passes < 5% rule: {signal['passes_spread_filter']})")
            print(f"  Conviction Score: {signal['conviction']}%")
            print(f"  Actionable: {signal['is_actionable']}")
        else:
            print("  No signal triggered (market neutral or low volatility).")

    print("\n Pipeline verification completed successfully!")


if __name__ == "__main__":
    test_full_pipeline()
