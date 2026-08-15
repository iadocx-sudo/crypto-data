#!/usr/bin/env python3
"""
Coinalyze(無料API) -> data/latest.json  【レート制限対応版】
- 無料枠 40req/分。呼び出し毎に必ず間隔を空け、429なら Retry-After 待って再試行。
- 銘柄シンボル書式は future-markets から自動取得（例 BTCUSDT_PERP.A）。
"""
import os, json, time, datetime, urllib.request, urllib.parse

KEY = os.environ["COINALYZE_KEY"]
BASE = "https://api.coinalyze.net/v1"
COINS = ["BTC", "ETH", "SOL", "LINK", "SUI", "AAVE", "TAO"]

now = int(time.time())
FROM = now - 35 * 86400
INTERVAL = "daily"
MAX_SYMS = 12          # 1コインあたり主要ペアのみ（レスポンス軽量化）
GAP = 2.0              # 呼び出し間隔（秒）= 約30req/分 <40

_last = [0.0]
def _throttle():
    wait = GAP - (time.time() - _last[0])
    if wait > 0: time.sleep(wait)
    _last[0] = time.time()

def get(path, params=None):
    p = dict(params or {}); p["api_key"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(p)
    for attempt in range(4):
        _throttle()
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                ra = int(e.headers.get("Retry-After", "5"))
                time.sleep(ra + 1); continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": str(e)}
    return {"error": "429 after retries"}

# --- シンボル取得 ---
markets = get("future-markets")
sym = {c: [] for c in COINS}
if isinstance(markets, list):
    for m in markets:
        b = m.get("base_asset") or m.get("base") or ""
        if b in COINS and m.get("is_perpetual", True):
            s = m.get("symbol")
            if s and len(sym[b]) < MAX_SYMS: sym[b].append(s)

def hist(path, syms):
    if not syms: return {"error": "no symbols"}
    return get(path, {"symbols": ",".join(syms), "interval": INTERVAL,
                      "from": FROM, "to": now, "convert_to_usd": "true"})

out = {"generated_at": datetime.datetime.utcnow().isoformat() + "Z",
       "markets_count": len(markets) if isinstance(markets, list) else markets,
       "coins": {}}

for c in COINS:
    s = sym[c]
    csv = ",".join(s)
    out["coins"][c] = {
        "symbols":         s,
        "open_interest":   get("open-interest", {"symbols": csv, "convert_to_usd": "true"}) if s else {"error": "no symbols"},
        "funding_rate":    get("funding-rate", {"symbols": csv}) if s else {"error": "no symbols"},
        "oi_history":      hist("open-interest-history", s),
        "funding_history": hist("funding-rate-history", s),
        "long_short_ratio":hist("long-short-ratio-history", s),
        "liquidation":     hist("liquidation-history", s),
        "ohlcv":           hist("ohlcv-history", s),  # CVD素材(買い/売り出来高)
    }

os.makedirs("data", exist_ok=True)
with open("data/latest.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("wrote data/latest.json")
