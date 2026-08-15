#!/usr/bin/env python3
"""
Coinalyze(無料API) -> data/latest.json
- 無料キーを環境変数 COINALYZE_KEY から読む（コードに書かない）
- base: https://api.coinalyze.net/v1 / 認証: ヘッダ or クエリ api_key / 40req/分
- 叩けなかった項目は {"error": "..."} として記録し、全体は落とさない
- 初回は future_markets も丸ごと保存する（銘柄シンボルの正確な書式を確認するため）
"""
import os, json, time, datetime, urllib.request, urllib.parse

KEY = os.environ["COINALYZE_KEY"]
BASE = "https://api.coinalyze.net/v1"
COINS = ["BTC", "ETH", "SOL", "LINK", "SUI", "AAVE", "TAO"]

now = int(time.time())
FROM = now - 35 * 86400          # 直近35日
INTERVAL = "daily"               # 1min,5min,15min,30min,1hour,4hour,daily 等

def get(path, params=None):
    p = dict(params or {}); p["api_key"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(p)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

# --- 銘柄シンボルを取得（例: "BTCUSDT_PERP.A" のような書式） ---
markets = get("future-markets")
sym_by_coin = {c: [] for c in COINS}
if isinstance(markets, list):
    for m in markets:
        base = m.get("base_asset") or m.get("base") or ""
        if base in COINS and m.get("is_perpetual", True):
            s = m.get("symbol")
            if s:
                sym_by_coin[base].append(s)

def hist(path, symbols):
    if not symbols:
        return {"error": "no symbols"}
    return get(path, {"symbols": ",".join(symbols[:20]),
                      "interval": INTERVAL, "from": FROM, "to": now,
                      "convert_to_usd": "true"})

out = {"generated_at": datetime.datetime.utcnow().isoformat() + "Z",
       "future_markets_raw": markets if not isinstance(markets, list) else f"{len(markets)} markets",
       "coins": {}}

for c in COINS:
    syms = sym_by_coin[c]
    out["coins"][c] = {
        "symbols":          syms,
        "open_interest":    get("open-interest", {"symbols": ",".join(syms[:20]), "convert_to_usd": "true"}) if syms else {"error": "no symbols"},
        "funding_rate":     get("funding-rate", {"symbols": ",".join(syms[:20])}) if syms else {"error": "no symbols"},
        "predicted_funding":get("predicted-funding-rate", {"symbols": ",".join(syms[:20])}) if syms else {"error": "no symbols"},
        "oi_history":       hist("open-interest-history", syms),
        "funding_history":  hist("funding-rate-history", syms),
        "long_short_ratio": hist("long-short-ratio-history", syms),
        "liquidation":      hist("liquidation-history", syms),
        # CVDの素材（買い/売り出来高）。CVD自体は読み取り側で (buy-sell) の累積で算出
        "ohlcv":            hist("ohlcv-history", syms),
    }
    time.sleep(1.6)  # 40req/分に収める

os.makedirs("data", exist_ok=True)
with open("data/latest.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("wrote data/latest.json")
