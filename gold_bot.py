import os
import time
import requests

# --- Config ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY")
CHAT_ID = "5873027607"
SYMBOL = "XAU/USD"
INTERVAL = "1h"
CHECK_INTERVAL = 300  # Check every 5 minutes

last_signal = None  # Track last signal to avoid duplicates
trade = {
    "active": False,
    "direction": None,
    "entry": None,
    "sl": None,
    "tp1": None, "tp1_hit": False,
    "tp2": None, "tp2_hit": False,
    "tp3": None, "tp3_hit": False,
}

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=10)
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_ema(period):
    try:
        url = (
            f"https://api.twelvedata.com/ema"
            f"?symbol={SYMBOL}&interval={INTERVAL}"
            f"&time_period={period}&outputsize=2"
            f"&apikey={TWELVE_DATA_KEY}"
        )
        res = requests.get(url, timeout=10)
        data = res.json()
        values = data.get("values", [])
        if values:
            return float(values[0]["ema"])
        return None
    except Exception as e:
        print(f"EMA error: {e}")
        return None

def check_trade_levels(price):
    if not trade["active"]:
        return

    direction = trade["direction"]
    sl = trade["sl"]

    # Check Stop Loss
    if (direction == "BUY" and price <= sl) or (direction == "SELL" and price >= sl):
        send_telegram(
            f"🛑 *STOP LOSS HIT*\n\n"
            f"📊 XAU/USD\n"
            f"💰 Price: *${price:,.2f}*\n"
            f"🛑 SL: *${sl:,.2f}*\n\n"
            f"❌ Trade closed at a loss\n"
            f"💪 Stay disciplined, next signal coming!"
        )
        trade["active"] = False
        return

    # Check TP1
    if not trade["tp1_hit"]:
        if (direction == "BUY" and price >= trade["tp1"]) or (direction == "SELL" and price <= trade["tp1"]):
            trade["tp1_hit"] = True
            send_telegram(
                f"✅ *TP1 HIT!*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Price: *${price:,.2f}*\n"
                f"🎯 TP1: *${trade['tp1']:,.2f}*\n\n"
                f"💡 Consider moving SL to breakeven\n"
                f"⏳ Waiting for TP2..."
            )

    # Check TP2
    if trade["tp1_hit"] and not trade["tp2_hit"]:
        if (direction == "BUY" and price >= trade["tp2"]) or (direction == "SELL" and price <= trade["tp2"]):
            trade["tp2_hit"] = True
            send_telegram(
                f"✅ *TP2 HIT!*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Price: *${price:,.2f}*\n"
                f"🎯 TP2: *${trade['tp2']:,.2f}*\n\n"
                f"💡 Consider taking partial profits\n"
                f"⏳ Waiting for TP3..."
            )

    # Check TP3
    if trade["tp2_hit"] and not trade["tp3_hit"]:
        if (direction == "BUY" and price >= trade["tp3"]) or (direction == "SELL" and price <= trade["tp3"]):
            trade["tp3_hit"] = True
            trade["active"] = False
            send_telegram(
                f"🏆 *TP3 HIT! FULL TARGET REACHED!*\n\n"
                f"📊 XAU/USD\n"
                f"💰 Price: *${price:,.2f}*\n"
                f"🎯 TP3: *${trade['tp3']:,.2f}*\n\n"
                f"🎉 Excellent trade! All targets hit!\n"
                f"💰 Trade closed in full profit!"
            )


    try:
        url = f"https://api.twelvedata.com/price?symbol={SYMBOL}&apikey={TWELVE_DATA_KEY}"
        res = requests.get(url, timeout=10)
        data = res.json()
        return float(data.get("price", 0))
    except Exception as e:
        print(f"Price error: {e}")
        return None

def run():
    global last_signal
    print("Gold EMA Bot started...")
    send_telegram("🥇 *Gold EMA Crossover Bot is live!*\nMonitoring XAU/USD on 1H chart...")

    while True:
        print("Checking EMAs...")
        ema20 = get_ema(20)
        ema50 = get_ema(50)
        price = get_current_price()

        print(f"EMA20: {ema20} | EMA50: {ema50} | Price: {price}")

        if ema20 and ema50 and price:
            # Stop loss and take profit levels
            sl_pips = 15  # $15 stop loss
            tp1_pips = 20  # $20 first target
            tp2_pips = 40  # $40 second target
            tp3_pips = 60  # $60 third target

            if ema20 > ema50 and last_signal != "BUY":
                last_signal = "BUY"
                sl = round(price - sl_pips, 2)
                tp1 = round(price + tp1_pips, 2)
                tp2 = round(price + tp2_pips, 2)
                tp3 = round(price + tp3_pips, 2)
                trade.update({"active": True, "direction": "BUY", "entry": price, "sl": sl, "tp1": tp1, "tp1_hit": False, "tp2": tp2, "tp2_hit": False, "tp3": tp3, "tp3_hit": False})
                msg = (
                    f"🟢 *GOLD BUY SIGNAL*\n\n"
                    f"📊 XAU/USD — 1H Chart\n"
                    f"💰 Entry Price: *${price:,.2f}*\n\n"
                    f"📈 EMA 20: {ema20:,.2f}\n"
                    f"📈 EMA 50: {ema50:,.2f}\n\n"
                    f"✅ *20 EMA crossed ABOVE 50 EMA*\n\n"
                    f"🎯 TP1: *${tp1:,.2f}*\n"
                    f"🎯 TP2: *${tp2:,.2f}*\n"
                    f"🎯 TP3: *${tp3:,.2f}*\n"
                    f"🛑 Stop Loss: *${sl:,.2f}*\n\n"
                    f"🔗 [View Chart](https://www.tradingview.com/chart/?symbol=XAUUSD)\n"
                    f"⚠️ _Always manage your risk_"
                )
                send_telegram(msg)

            elif ema20 < ema50 and last_signal != "SELL":
                last_signal = "SELL"
                sl = round(price + sl_pips, 2)
                tp1 = round(price - tp1_pips, 2)
                tp2 = round(price - tp2_pips, 2)
                tp3 = round(price - tp3_pips, 2)
                trade.update({"active": True, "direction": "SELL", "entry": price, "sl": sl, "tp1": tp1, "tp1_hit": False, "tp2": tp2, "tp2_hit": False, "tp3": tp3, "tp3_hit": False})
                msg = (
                    f"🔴 *GOLD SELL SIGNAL*\n\n"
                    f"📊 XAU/USD — 1H Chart\n"
                    f"💰 Entry Price: *${price:,.2f}*\n\n"
                    f"📉 EMA 20: {ema20:,.2f}\n"
                    f"📉 EMA 50: {ema50:,.2f}\n\n"
                    f"✅ *20 EMA crossed BELOW 50 EMA*\n\n"
                    f"🎯 TP1: *${tp1:,.2f}*\n"
                    f"🎯 TP2: *${tp2:,.2f}*\n"
                    f"🎯 TP3: *${tp3:,.2f}*\n"
                    f"🛑 Stop Loss: *${sl:,.2f}*\n\n"
                    f"🔗 [View Chart](https://www.tradingview.com/chart/?symbol=XAUUSD)\n"
                    f"⚠️ _Always manage your risk_"
                )
                send_telegram(msg)
            else:
                print(f"No crossover detected. Last signal: {last_signal}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()
