import os
import time
import requests
import pandas as pd

# --- Config ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY")
CHAT_ID = os.environ.get("CHAT_ID", "-1003576401725")
SYMBOL = "XAU/USD"
INTERVAL = "1h"
CHECK_INTERVAL = 300
RETEST_TOLERANCE = 8.0
MIN_LEVEL_TOUCHES = 3
LOOKBACK = 15
FIXED_SL = 50
FIXED_TP = 150

active_trade = None
seen_levels = set()

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=10)
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_data():
    try:
        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={SYMBOL}&interval={INTERVAL}"
            f"&outputsize=200&apikey={TWELVE_DATA_KEY}"
        )
        res = requests.get(url, timeout=15)
        data = res.json()
        values = data.get("values", [])
        if not values:
            return pd.DataFrame()
        df = pd.DataFrame(values)
        if "datetime" not in df.columns:
            df = df.rename(columns={df.columns[0]: "datetime"})
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["open"]  = df["open"].astype(float)
        df["high"]  = df["high"].astype(float)
        df["low"]   = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df = df.sort_values("datetime").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Data error: {e}")
        return pd.DataFrame()

def get_current_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol={SYMBOL}&apikey={TWELVE_DATA_KEY}"
        res = requests.get(url, timeout=10)
        return float(res.json().get("price", 0))
    except:
        return 0

def find_key_levels(df):
    levels = []
    for i in range(LOOKBACK, len(df) - LOOKBACK):
        if df["high"].iloc[i] == df["high"].iloc[i-LOOKBACK:i+LOOKBACK+1].max():
            levels.append({"price": df["high"].iloc[i], "idx": i, "type": "resistance"})
        if df["low"].iloc[i] == df["low"].iloc[i-LOOKBACK:i+LOOKBACK+1].min():
            levels.append({"price": df["low"].iloc[i], "idx": i, "type": "support"})
    return levels

def count_touches(df, level_price, start_idx, end_idx, level_type):
    touches = 0
    for i in range(start_idx, end_idx):
        if level_type == "resistance" and abs(df["high"].iloc[i] - level_price) <= RETEST_TOLERANCE:
            touches += 1
        elif level_type == "support" and abs(df["low"].iloc[i] - level_price) <= RETEST_TOLERANCE:
            touches += 1
    return touches

def check_breakout(df, level_price, level_type, idx):
    close = df["close"].iloc[idx]
    if level_type == "resistance" and close > level_price + RETEST_TOLERANCE:
        return True
    if level_type == "support" and close < level_price - RETEST_TOLERANCE:
        return True
    return False

def check_retest(df, level_price, level_type, idx):
    high  = df["high"].iloc[idx]
    low   = df["low"].iloc[idx]
    close = df["close"].iloc[idx]
    if level_type == "resistance":
        retested = abs(low - level_price) <= RETEST_TOLERANCE or abs(close - level_price) <= RETEST_TOLERANCE
        return retested and close > level_price
    if level_type == "support":
        retested = abs(high - level_price) <= RETEST_TOLERANCE or abs(close - level_price) <= RETEST_TOLERANCE
        return retested and close < level_price
    return False

def scan_for_signal(df):
    global seen_levels
    levels = find_key_levels(df)

    for level in levels:
        level_price = round(level["price"], 2)
        level_type  = level["type"]
        level_idx   = level["idx"]
        level_key   = f"{level_price}_{level_type}"

        if level_key in seen_levels:
            continue

        touches = count_touches(df, level_price, max(0, level_idx - 20), level_idx, level_type)
        if touches < MIN_LEVEL_TOUCHES:
            continue

        for b_idx in range(level_idx + 1, min(level_idx + 80, len(df) - 5)):
            if check_breakout(df, level_price, level_type, b_idx):
                for r_idx in range(b_idx + 1, min(b_idx + 30, len(df) - 2)):
                    if check_retest(df, level_price, level_type, r_idx):
                        if r_idx >= len(df) - 3:
                            entry = df["close"].iloc[-1]
                            direction = "BUY" if level_type == "resistance" else "SELL"
                            sl = entry - FIXED_SL if direction == "BUY" else entry + FIXED_SL
                            tp = entry + FIXED_TP if direction == "BUY" else entry - FIXED_TP
                            seen_levels.add(level_key)
                            return {
                                "direction": direction,
                                "entry": round(entry, 2),
                                "sl": round(sl, 2),
                                "tp": round(tp, 2),
                                "level": level_price,
                                "level_type": level_type
                            }
                        break
                break
    return None

def check_active_trade(price):
    global active_trade
    if not active_trade:
        return

    direction = active_trade["direction"]
    sl = active_trade["sl"]
    tp = active_trade["tp"]
    entry = active_trade["entry"]

    if direction == "BUY":
        if price <= sl:
            send_telegram(
                f"🛑 *STOP LOSS HIT*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Entry: ${entry}\n"
                f"🛑 SL: ${sl}\n"
                f"❌ Loss: -${FIXED_SL}\n\n"
                f"💪 Stay disciplined, next signal coming!"
            )
            active_trade = None
        elif price >= tp:
            send_telegram(
                f"🏆 *TAKE PROFIT HIT!*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Entry: ${entry}\n"
                f"🎯 TP: ${tp}\n"
                f"✅ Profit: +${FIXED_TP}\n\n"
                f"🎉 Great trade!"
            )
            active_trade = None

    elif direction == "SELL":
        if price >= sl:
            send_telegram(
                f"🛑 *STOP LOSS HIT*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Entry: ${entry}\n"
                f"🛑 SL: ${sl}\n"
                f"❌ Loss: -${FIXED_SL}\n\n"
                f"💪 Stay disciplined, next signal coming!"
            )
            active_trade = None
        elif price <= tp:
            send_telegram(
                f"🏆 *TAKE PROFIT HIT!*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Entry: ${entry}\n"
                f"🎯 TP: ${tp}\n"
                f"✅ Profit: +${FIXED_TP}\n\n"
                f"🎉 Great trade!"
            )
            active_trade = None

def run():
    global active_trade
    print("Gold Break & Retest Bot started...")
    send_telegram(
        "🥇 *Gold Break & Retest Signal Bot is live!*\n"
        "📊 Monitoring XAU/USD on 1H chart\n"
        "📌 Strategy: Break & Retest\n"
        f"🛑 SL: ${FIXED_SL} | 🎯 TP: ${FIXED_TP} | RR: 1:3"
    )

    while True:
        print("Scanning for signals...")
        df = get_data()
        price = get_current_price()

        if df.empty or price == 0:
            print("No data received. Retrying...")
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"Current price: ${price}")

        if active_trade:
            check_active_trade(price)
        else:
            signal = scan_for_signal(df)
            if signal:
                active_trade = signal
                direction = signal["direction"]
                emoji = "🟢" if direction == "BUY" else "🔴"
                level_label = "Resistance → Support" if signal["level_type"] == "resistance" else "Support → Resistance"

                send_telegram(
                    f"{emoji} *GOLD {direction} SIGNAL*\n\n"
                    f"📊 XAU/USD — 1H Chart\n"
                    f"📌 Setup: *Break & Retest*\n"
                    f"🔑 Level: ${signal['level']} ({level_label})\n\n"
                    f"💰 Entry: *${signal['entry']}*\n"
                    f"🎯 Take Profit: *${signal['tp']}*\n"
                    f"🛑 Stop Loss: *${signal['sl']}*\n\n"
                    f"📊 RR: 1:3\n"
                    f"🔗 [View Chart](https://www.tradingview.com/chart/?symbol=XAUUSD)\n"
                    f"⚠️ _Always manage your risk_"
                )
                print(f"Signal sent: {direction} at ${signal['entry']}")
            else:
                print("No signal found this scan")

        print(f"Sleeping {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()
