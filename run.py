import os
import sys
import warnings
from pathlib import Path

# Suppress CUDA architecture advisory warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import time
    
    from app.config import config_manager
    watchlist = config_manager.get_watchlist()
    cat_counts = {}
    for item in watchlist:
        c = item.get("category", "Other")
        cat_counts[c] = cat_counts.get(c, 0) + 1
    cat_str = ", ".join(f"{k} ({v})" for k, v in sorted(cat_counts.items()))

    print("=" * 65)
    print("   AI QUANT TRADING FORECAST TERMINAL")
    print("   500 Historical Candles -> 5 Future Forecasted Candles")
    print("=" * 65)
    print(" * Web Dashboard:   http://localhost:8000")
    print(" * API Docs:        http://localhost:8000/docs")
    print(f" * Universe:        FundedNext 2-Step Stellar CFDs ({len(watchlist)} Assets)")
    print(f" * Categories:      {cat_str}")
    print(" * Liquidity Mode:  London & New York Overlap Detector Active")
    print(" * Guardrail:       Spread < 5% of Stop-Loss Distance")
    print(" * Rollover Filter: 20:00 - 23:00 UTC Spread Risk Guard Active")
    print("=" * 65)
    
    # Auto-launch browser after brief pause
    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
