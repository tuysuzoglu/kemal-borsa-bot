import os, time, json, threading, requests
from datetime import datetime, date
from flask import Flask

BUDGET_TL = 5000.0
USE_PERCENT = 0.25
PROFIT_TRIGGER = 3.0
TRAILING_DROP = 0.8
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

TRADE_LOG = "trade_history.json"
STATE_FILE = "bot_state.json"
app = Flask(__name__)

@app.route('/')
def home():
    return f"BOT AKTIF - {datetime.now()}"

def load_json(p, d):
    try:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return d

def save_json(p, data):
    with open(p, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)

def get_btc_price_tl():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCTRY", timeout=5)
        if r.status_code==200: return float(r.json()['price'])
    except: pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=try", timeout=10)
        return float(r.json()['bitcoin']['try'])
    except: return None

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID: 
        print(f"[TG] {text}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e: print(e)

def telegram_listener():
    offset=0
    while True:
        try:
            if not BOT_TOKEN: time.sleep(10); continue
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30", timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"]+1
                msg = upd.get("message", {})
                text = msg.get("text","")
                if text in ["/durum","/start","/bakiye"]:
                    send_telegram(f"🤖 BOT AKTIF\nFiyat: {get_btc_price_tl()}\nTest: True")
        except: time.sleep(5)

def trading_loop():
    state = load_json(STATE_FILE, {"balance": BUDGET_TL, "position": None})
    while True:
        try:
            price = get_btc_price_tl()
            if not price: time.sleep(10); continue
            print(f"Fiyat {price}")
            time.sleep(20)
        except Exception as e:
            print(e); time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
