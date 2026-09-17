import json
from pathlib import Path

forex_symbols = [
    ('AUDCAD', 'AUD/CAD', 0.02), ('AUDCHF', 'AUD/CHF', 0.02), ('AUDJPY', 'AUD/JPY', 0.018),
    ('AUDNZD', 'AUD/NZD', 0.022), ('AUDSGD', 'AUD/SGD', 0.025), ('AUDUSD', 'AUD/USD', 0.012),
    ('CADCHF', 'CAD/CHF', 0.022), ('CADJPY', 'CAD/JPY', 0.02), ('CHFJPY', 'CHF/JPY', 0.02),
    ('EURAUD', 'EUR/AUD', 0.02), ('EURCAD', 'EUR/CAD', 0.02), ('EURCHF', 'EUR/CHF', 0.018),
    ('EURGBP', 'EUR/GBP', 0.015), ('EURHKD', 'EUR/HKD', 0.03), ('EURJPY', 'EUR/JPY', 0.015),
    ('EURNOK', 'EUR/NOK', 0.035), ('EURNZD', 'EUR/NZD', 0.025), ('EURSGD', 'EUR/SGD', 0.025),
    ('EURUSD', 'EUR/USD', 0.008), ('EURPLN', 'EUR/PLN', 0.035), ('EURTRY', 'EUR/TRY', 0.05),
    ('EURSEK', 'EUR/SEK', 0.035), ('GBPAUD', 'GBP/AUD', 0.022), ('GBPCAD', 'GBP/CAD', 0.022),
    ('GBPCHF', 'GBP/CHF', 0.022), ('GBPJPY', 'GBP/JPY', 0.018), ('GBPNZD', 'GBP/NZD', 0.028),
    ('GBPSGD', 'GBP/SGD', 0.028), ('GBPUSD', 'GBP/USD', 0.012), ('NZDCAD', 'NZD/CAD', 0.022),
    ('NZDCHF', 'NZD/CHF', 0.022), ('NZDJPY', 'NZD/JPY', 0.022), ('NZDSGD', 'NZD/SGD', 0.028),
    ('NZDUSD', 'NZD/USD', 0.018), ('SGDJPY', 'SGD/JPY', 0.025), ('USDCAD', 'USD/CAD', 0.015),
    ('USDCHF', 'USD/CHF', 0.015), ('USDCNH', 'USD/CNH', 0.025), ('USDDKK', 'USD/DKK', 0.03),
    ('USDHUF', 'USD/HUF', 0.035), ('USDJPY', 'USD/JPY', 0.01), ('USDMXN', 'USD/MXN', 0.03),
    ('USDNOK', 'USD/NOK', 0.035), ('USDSGD', 'USD/SGD', 0.022), ('USDZAR', 'USD/ZAR', 0.035),
    ('USDSEK', 'USD/SEK', 0.035), ('USDPLN', 'USD/PLN', 0.035), ('USDTRY', 'USD/TRY', 0.05)
]

indices_symbols = [
    ('US30', 'Wall Street 30 (Dow)', 0.01), ('NAS100', 'US Tech 100 (Nasdaq)', 0.012),
    ('SPX500', 'US 500 (S&P)', 0.008), ('GER40', 'Germany 40 (DAX)', 0.012),
    ('UK100', 'UK 100 (FTSE)', 0.015), ('FRA40', 'France 40 (CAC)', 0.015),
    ('EUSTX50', 'Euro Stoxx 50', 0.015), ('JP225', 'Japan 225 (Nikkei)', 0.018),
    ('HK50', 'Hong Kong 50 (Hang Seng)', 0.025), ('AUS200', 'Australia 200', 0.018),
    ('US2000', 'US Small Cap 2000', 0.02), ('SWI20', 'Switzerland 20', 0.02),
    ('NTH25', 'Netherlands 25', 0.02), ('ESP35', 'Spain 35 (IBEX)', 0.025)
]

crypto_symbols = [
    ('BTCUSD', 'Bitcoin', 0.02), ('ETHUSD', 'Ethereum', 0.025),
    ('LTCUSD', 'Litecoin', 0.035), ('XRPUSD', 'Ripple', 0.04),
    ('ADAUSD', 'Cardano', 0.04), ('DOGUSD', 'Dogecoin', 0.045),
    ('XLMUSD', 'Stellar Lumens', 0.045), ('LNKUSD', 'Chainlink', 0.04),
    ('XMRUSD', 'Monero', 0.05)
]

stock_symbols = [
    ('AAPL', 'Apple Inc.', 0.015), ('AMZN', 'Amazon.com', 0.015), ('GOOG', 'Alphabet Inc.', 0.015),
    ('MSFT', 'Microsoft Corp.', 0.015), ('NVDA', 'NVIDIA Corp.', 0.018), ('TSLA', 'Tesla Inc.', 0.02),
    ('AMD', 'Advanced Micro Devices', 0.02), ('META', 'Meta Platforms', 0.018), ('BABA', 'Alibaba Group', 0.025),
    ('NFLX', 'Netflix Inc.', 0.02), ('INTC', 'Intel Corp.', 0.02), ('NKE', 'Nike Inc.', 0.02),
    ('KO', 'Coca-Cola Co.', 0.015), ('SPCX', 'Virgin Galactic', 0.04),
    ('MBG', 'Mercedes-Benz Group', 0.025), ('BAYN', 'Bayer AG', 0.025),
    ('MC', 'LVMH', 0.02), ('VOW3', 'Volkswagen AG', 0.025),
    ('ADS', 'Adidas AG', 0.025), ('BMW', 'BMW AG', 0.025)
]

new_watchlist = []
for s, n, sp in forex_symbols:
    new_watchlist.append({'symbol': s, 'name': n, 'category': 'Forex', 'active': True, 'est_spread_pct': sp})
for s, n, sp in indices_symbols:
    new_watchlist.append({'symbol': s, 'name': n, 'category': 'Indices', 'active': True, 'est_spread_pct': sp})
for s, n, sp in crypto_symbols:
    new_watchlist.append({'symbol': s, 'name': n, 'category': 'Crypto', 'active': True, 'est_spread_pct': sp})
for s, n, sp in stock_symbols:
    new_watchlist.append({'symbol': s, 'name': n, 'category': 'Stocks', 'active': True, 'est_spread_pct': sp})

config_path = Path(__file__).resolve().parent / 'config.json'
with open(config_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

cfg['watchlist'] = new_watchlist
with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2)

print(f"Successfully saved {len(new_watchlist)} FundedNext CFD symbols into {config_path}")
