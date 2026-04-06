#!/usr/bin/env python3
"""Test if Binance can provide 3 years of data"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from datetime import datetime, timezone, timedelta

end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=1095)  # 3 years

print(f"Attempting to fetch BTCUSDT 4h from Binance:")
print(f"  Start: {start_time}")
print(f"  End:   {end_time}")
print(f"  Duration: {(end_time - start_time).days} days")
print()

url = "https://api.binance.com/api/v3/klines"
params = {
    "symbol": "BTCUSDT",
    "interval": "4h",
    "startTime": int(start_time.timestamp() * 1000),
    "endTime": int(end_time.timestamp() * 1000),
    "limit": 1000
}

try:
    print("Making test request to Binance...")
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"  ✅ Success! Got {len(data)} candles")
        if data:
            first_ts = datetime.fromtimestamp(data[0][0]/1000, tz=timezone.utc)
            last_ts = datetime.fromtimestamp(data[-1][0]/1000, tz=timezone.utc)
            print(f"  Range: {first_ts} → {last_ts}")
    else:
        print(f"  ❌ Error: {resp.status_code}")
        print(resp.text)
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()
