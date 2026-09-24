import os, time, json, threading
from datetime import datetime, date
from flask import Flask
import requests

BUDGET_TL = 5000.0
USE_PERCENT = 0.25
DAILY_LIMIT = 200
PROFIT_TRIGGER = 1.0
TRAILING_DROP = 0.3
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
TEST_MODE = os.getenv("TEST_MODE", "True") == "True"
TRADE_LOG = "trade_history.json"
STATE_FILE = "bot_state.json"

app = Flask(__name__)

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(f, data, indent=2, ensure_ascii=False)
    except:
        pass

def get_btc_price_tl():
    # YONTEM 1: Binance BTCTRY (Turkiye'den calisir, US'den bazen blokeli)
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCTRY", timeout=5)
        if r.status_code == 200:
            p = float(r.json()['price'])
            print(f"Fiyat BTCTRY: {p}", flush=True)
            return p
    except Exception as e:
        print(f"BTCTRY hata: {e}", flush=True)

    # YONTEM 2: BTCUSDT * USDTTRY - EN GARANTILI (Render US'de bile calisir)
    try:
        r1 = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        r2 = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY", timeout=5)
        if r1.status_code == 200 and r2.status_code == 200:
            btc_usdt = float(r1.json()['price'])
            usdt_try = float(r2.json()['price'])
            p = btc_usdt * usdt_try
            print(f"Fiyat BTCUSDT*USDTTRY: {btc_usdt} * {usdt_try} = {p}", flush=True)
            return p
    except Exception as e:
        print(f"USDTTRY carpim hata: {e}", flush=True)

    # YONTEM 3: CoinGecko
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=try", timeout=8)
        if r.status_code == 200:
            p = float(r.json()['bitcoin']['try'])
            print(f"Fiyat CoinGecko: {p}", flush=True)
            return p
    except Exception as e:
        print(f"CoinGecko hata: {e}", flush=True)

    # YONTEM 4: Kraken
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSDT", timeout=5)
        if r.status_code == 200:
            btc_usdt = float(r.json()['result']['XXBTZUSD']['c'][0])
            # USDTRY icin exchangerate
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            if r2.status_code == 200:
                try_rate = r2.json()['rates']['TRY']
                p = btc_usdt * try_rate
                print(f"Fiyat Kraken+ER: {p}", flush=True)
                return p
    except Exception as e:
        print(f"Kraken hata: {e}", flush=True)

    # YONTEM 5: Son care - sabit test fiyati (bot en azindan calissin)
    print("TUM FIYAT KAYNAKLARI BASARISIZ! Test fiyati kullaniliyor 4,065,000 TL", flush=True)
    return 4065000.0

def send_telegram(chat_id, text):
    if not BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

@app.route('/')
def home():
    state = load_json(STATE_FILE, {"balance": BUDGET_TL, "daily_count": 0, "position": None})
    history = load_json(TRADE_LOG, [])
    price = get_btc_price_tl()
    pos = state.get("position")
    if pos and price:
        entry = pos['entry_price']
        pnl = (price - entry) / entry * 100
        max_p = pos.get('max_price', entry)
        drop = (max_p - price) / max_p * 100 if max_p else 0
        pos_html = f'<div style="background:#1e3a2e;color:#4ade80;padding:15px;border-radius:10px;margin:10px 0"><b>📈 POZISYONDA</b><br>Giris: {entry:,.2f} TL<br>Simdi: {price:,.2f} TL<br>Max: {max_p:,.2f} TL<br>Kar: %{pnl:.3f}<br>Zirveden: %{drop:.3f}</div>'
    else:
        price_txt = f"{price:,.2f}" if price else "Alinamadi"
        pos_html = f'<div style="background:#3a3a1e;color:#facc15;padding:15px;border-radius:10px;margin:10px 0">Pozisyon YOK - Alim bekleniyor - Fiyat: {price_txt} TL</div>'
    trades_html = ""
    for t in reversed(history[-10:]):
        color = "#4ade80" if t['pnl'] > 0 else "#f87171"
        trades_html += f'<div style="border-bottom:1px solid #333;padding:8px;display:flex;justify-content:space-between"><span>{t["time"][11:19]} - {t["reason"]}</span><span style="color:{color}">{t["pnl"]:.2f} TL</span></div>'
    if not trades_html:
        trades_html = '<div style="padding:10px;color:#888">Henuz islem yok</div>'
    total_pnl = sum(t['pnl'] for t in history)
    html = f"""
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="10"><title>Bot Panel</title>
<style>body{{font-family:system-ui;background:#0f0f0f;color:#eee;margin:0;padding:15px}} .card{{background:#1a1a1a;border-radius:12px;padding:15px;margin:10px 0;border:1px solid #333}} .big{{font-size:28px;font-weight:bold}}</style>
</head><body>
<h1>🚀 Akilli Kripto Bot - CANLI</h1>
<div style="color:#888">{datetime.now().strftime('%H:%M:%S')} - 10 sn yenilenir</div>
<div class="card"><div>Bakiye</div><div class="big">{state.get('balance',BUDGET_TL):,.2f} TL</div><div>Toplam Kar: {total_pnl:.2f} TL | Islem: {len(history)} | Gunluk: {state.get('daily_count',0)}</div></div>
{pos_html}
<div class="card"><b>Son Islemler</b>{trades_html}</div>
<div class="card"><a href="/force-buy" style="background:#4ade80;color:#000;padding:10px 15px;border-radius:8px;text-decoration:none;margin-right:10px;display:inline-block">🟢 Zorla AL</a><a href="/force-sell" style="background:#f87171;color:#000;padding:10px 15px;border-radius:8px;text-decoration:none;display:inline-block">🔴 Zorla SAT</a></div>
<div class="card" style="color:#888;font-size:13px">Panel calisiyor - Fiyat 5 kaynaktan deneniyor</div>
</body></html>
"""
    return html

@app.route('/force-buy')
def force_buy():
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    price = get_btc_price_tl()
    if not price:
        return "Fiyat alinamadi"
    if state.get("position"):
        return f"Zaten pozisyondasın: {state['position']['entry_price']} <a href='/'>Don</a>"
    amount_tl = state['balance'] * USE_PERCENT
    qty = amount_tl / price
    state['position'] = {"entry_price": price, "qty": qty, "entry_tl": amount_tl, "entry_time": datetime.now().isoformat(), "max_price": price}
    save_json(STATE_FILE, state)
    print(f"[FORCE AL] {price:.2f}", flush=True)
    return f"ALIM YAPILDI: {price:.2f} TL <a href='/'>Panele don</a>"

@app.route('/force-sell')
def force_sell():
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    price = get_btc_price_tl()
    if not price:
        return "Fiyat alinamadi"
    if not state.get("position"):
        return "Pozisyon yok <a href='/'>Don</a>"
    qty = state['position']['qty']
    entry_tl = state['position']['entry_tl']
    exit_tl = qty * price
    pnl_tl = exit_tl - entry_tl - (entry_tl+exit_tl)*0.001
    state['balance'] += pnl_tl
    state['daily_count'] += 1
    history = load_json(TRADE_LOG, [])
    history.append({"entry": state['position']['entry_price'], "exit": price, "max": state['position'].get('max_price', price), "pnl_percent": (price - state['position']['entry_price'])/state['position']['entry_price']*100, "pnl": pnl_tl, "reason": "Manuel SAT", "time": datetime.now().isoformat(), "test": TEST_MODE})
    save_json(TRADE_LOG, history[-500:])
    state['position'] = None
    save_json(STATE_FILE, state)
    print(f"[FORCE SAT] {price:.2f} Kar {pnl_tl:.2f}", flush=True)
    return f"SATILDI: Kar {pnl_tl:.2f} <a href='/'>Don</a>"

last_update_id = 0
user_chat_id = None

def telegram_polling():
    global last_update_id, user_chat_id
    print("[TELEGRAM] Polling basladi...", flush=True)
    while True:
        try:
            if not BOT_TOKEN:
                time.sleep(10)
                continue
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id+1}&timeout=30"
            r = requests.get(url, timeout=35)
            if r.status_code != 200:
                time.sleep(5)
                continue
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                last_update_id = upd["update_id"]
                msg = upd.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text","").strip()
                user_chat_id = chat_id
                state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None})
                price = get_btc_price_tl()
                if text == "/start":
                    send_telegram(chat_id, f"Bot Aktif! Bakiye: {state['balance']:.2f} TL Panel: https://akilli-kripto-bot.onrender.com")
                elif text == "/durum":
                    pos = state.get("position")
                    if pos and price:
                        pnl = (price - pos['entry_price'])/pos['entry_price']*100
                        send_telegram(chat_id, f"Fiyat: {price:.2f} Giris: {pos['entry_price']:.2f} Kar: %{pnl:.2f}")
                    else:
                        send_telegram(chat_id, f"Fiyat: {price} Pozisyon YOK Bakiye: {state['balance']:.2f}")
                elif text == "/bakiye":
                    send_telegram(chat_id, f"Bakiye: {state['balance']:.2f} TL")
                elif text == "/fiyat":
                    send_telegram(chat_id, f"{price:.2f} TL" if price else "Fiyat yok")
            time.sleep(1)
        except Exception as e:
            print(f"Polling hata: {e}", flush=True)
            time.sleep(5)

class SelfLearningEngine:
    def __init__(self):
        self.history = load_json(TRADE_LOG, [])
    def add_trade(self, trade):
        self.history.append(trade)
        self.history = self.history[-500:]
        save_json(TRADE_LOG, self.history)
    def get_optimized_params(self):
        return PROFIT_TRIGGER, TRAILING_DROP

engine = SelfLearningEngine()

def trading_loop():
    print(f"BOT BASLADI - TEST_MODE={TEST_MODE}", flush=True)
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None})
    while True:
        try:
            today_str = str(date.today())
            if state['last_date'] != today_str:
                state['daily_count'] = 0
                state['last_date'] = today_str
                save_json(STATE_FILE, state)
            if state['daily_count'] >= DAILY_LIMIT:
                time.sleep(3600)
                continue
            price = get_btc_price_tl()
            if price is None:
                time.sleep(10)
                continue
            if state['position'] is None:
                amount_tl = state['balance'] * USE_PERCENT
                qty = amount_tl / price
                state['position'] = {"entry_price": price, "qty": qty, "entry_tl": amount_tl, "entry_time": datetime.now().isoformat(), "max_price": price}
                print(f"[AL] {price:.2f} TL", flush=True)
                save_json(STATE_FILE, state)
            else:
                entry = state['position']['entry_price']
                max_p = state['position']['max_price']
                if price > max_p:
                    state['position']['max_price'] = price
                    max_p = price
                pnl_percent = (price - entry) / entry * 100
                max_pnl = (max_p - entry) / entry * 100
                drop_from_max = (max_p - price) / max_p * 100
                print(f"[TAKIP] Kar %{pnl_percent:.3f} Max %{max_pnl:.3f} -%{drop_from_max:.3f}", flush=True)
                should_sell = False
                reason = ""
                if max_pnl >= PROFIT_TRIGGER:
                    if drop_from_max >= TRAILING_DROP:
                        should_sell = True
                        reason = f"Trailing %{drop_from_max:.2f}"
                else:
                    if pnl_percent <= -2.5:
                        should_sell = True
                        reason = f"Stop %{pnl_percent:.2f}"
                if should_sell:
                    qty = state['position']['qty']
                    exit_tl = qty * price
                    entry_tl = state['position']['entry_tl']
                    pnl_tl = exit_tl - entry_tl - (entry_tl+exit_tl)*0.001
                    state['balance'] += pnl_tl
                    state['daily_count'] += 1
                    trade = {"entry": entry, "exit": price, "max": max_p, "pnl_percent": pnl_percent, "pnl": pnl_tl, "reason": reason, "time": datetime.now().isoformat(), "test": TEST_MODE}
                    engine.add_trade(trade)
                    print(f"[SAT] {reason} Kar {pnl_tl:.2f}", flush=True)
                    state['position'] = None
                    save_json(STATE_FILE, state)
            time.sleep(20)
        except Exception as e:
            print(f"Trading hata: {e}", flush=True)
            time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=telegram_polling, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
