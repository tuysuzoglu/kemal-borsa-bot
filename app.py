"""
AKILLI KRIPTO BOT - TEST MODU - DUZELTILMIS VERSIYON
- Hardcoded token kaldirildi (güvenli)
- /start, /durum, /bakiye komutlari eklendi
- Render'da 7/24 calisir
"""
import os
import time
import json
import threading
from datetime import datetime, date
from flask import Flask
import requests

# --- AYARLAR ---
BUDGET_TL = 5000.0
USE_PERCENT = 0.25
DAILY_LIMIT = 200
PROFIT_TRIGGER = 3.0
TRAILING_DROP = 0.8

# GUVENLIK: Token asla koda yazilmaz, sadece Render Environment'dan gelir
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    print("UYARI: BOT_TOKEN bulunamadi! Render Environment'a ekleyin.")

TEST_MODE = os.getenv("TEST_MODE", "True") == "True"

TRADE_LOG = "trade_history.json"
STATE_FILE = "bot_state.json"

app = Flask(__name__)

@app.route('/')
def home():
    return f"BOT AKTIF - TEST_MODE={TEST_MODE} - {datetime.now()} - Komutlar: /start /durum /bakiye"

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
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Kayit hatasi: {e}")

def get_btc_price_tl():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCTRY", timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=try", timeout=10)
        return float(r.json()['bitcoin']['try'])
    except:
        return None

def send_telegram(chat_id, text):
    if not BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram hata: {e}")

# --- TELEGRAM KOMUTLARI ICIN POLLING ---
last_update_id = 0
user_chat_id = None  # son mesaj atan kisinin id'si

def telegram_polling():
    global last_update_id, user_chat_id
    print("[TELEGRAM] Polling basladi...")
    while True:
        try:
            if not BOT_TOKEN:
                time.sleep(10)
                continue
            
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id+1}&timeout=30"
            r = requests.get(url, timeout=35)
            if r.status_code != 200:
                if r.status_code == 401:
                    print("HATA: BOT_TOKEN gecersiz! BotFather'dan yeni token alip Render'a ekleyin.")
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
                user_chat_id = chat_id  # hatirla

                state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
                price = get_btc_price_tl()

                if text == "/start":
                    send_telegram(chat_id, f"🚀 *Akilli Kripto Bot Aktif!*\n\nMod: {'TEST - Sanal Para' if TEST_MODE else 'LIVE - Gercek Para'}\nButce: {BUDGET_TL} TL\nKasa Kullanimi: %{USE_PERCENT*100}\nKar Tetik: %{PROFIT_TRIGGER}\nTrailing: %{TRAILING_DROP}\nGunluk Limit: {DAILY_LIMIT}\n\nKomutlar:\n/durum - Anlik durum\n/bakiye - Bakiye ve pozisyon\n/fiyat - BTC/TRY fiyati\n/stop - Botu durdur (manuel)\n\nBot su an calisiyor ✅")

                elif text == "/durum":
                    pos = state.get("position")
                    if pos:
                        pnl = (price - pos['entry_price'])/pos['entry_price']*100 if price else 0
                        send_telegram(chat_id, f"📊 *Durum*\nFiyat: {price:.2f} TL\nGiris: {pos['entry_price']:.2f} TL\nKar: %{pnl:.2f}\nMax: {pos['max_price']:.2f}\nGunluk Islem: {state['daily_count']}/{DAILY_LIMIT}")
                    else:
                        send_telegram(chat_id, f"📊 *Durum*\nFiyat: {price:.2f} TL\nPozisyon: YOK - Alim bekleniyor\nBakiye: {state['balance']:.2f} TL\nGunluk: {state['daily_count']}/{DAILY_LIMIT}")

                elif text == "/bakiye":
                    send_telegram(chat_id, f"💰 Bakiye: {state['balance']:.2f} TL\nGunluk Islem: {state['daily_count']}")

                elif text == "/fiyat":
                    send_telegram(chat_id, f"₿ BTC/TRY: {price:.2f} TL" if price else "Fiyat alinamadi")

                elif text.startswith("/"):
                    send_telegram(chat_id, "Bilinmeyen komut. /start yaz")

            time.sleep(1)

        except Exception as e:
            print(f"Polling hata: {e}")
            time.sleep(5)

class SelfLearningEngine:
    def __init__(self):
        self.history = load_json(TRADE_LOG, [])

    def add_trade(self, trade):
        self.history.append(trade)
        self.history = self.history[-500:]
        save_json(TRADE_LOG, self.history)

    def get_optimized_params(self):
        if len(self.history) < 20:
            return PROFIT_TRIGGER, TRAILING_DROP
        recent = self.history[-50:]
        wins = [t for t in recent if t['pnl'] > 0]
        win_rate = len(wins) / len(recent) * 100
        if win_rate < 45:
            new_trailing = min(1.5, TRAILING_DROP + 0.1)
        elif win_rate > 65:
            new_trailing = max(0.4, TRAILING_DROP - 0.1)
        else:
            new_trailing = TRAILING_DROP
        print(f"[LEARNING] WinRate %{win_rate:.1f} - Trailing %{new_trailing:.2f}")
        return PROFIT_TRIGGER, new_trailing

engine = SelfLearningEngine()

def trading_loop():
    print(f"BOT BASLADI - TEST_MODE={TEST_MODE}")
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    
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

            profit_trigger, trailing_drop = engine.get_optimized_params()

            if state['position'] is None:
                amount_tl = state['balance'] * USE_PERCENT
                if amount_tl < 100:
                    time.sleep(60)
                    continue
                
                qty = amount_tl / price
                commission = amount_tl * 0.001
                
                state['position'] = {
                    "entry_price": price,
                    "qty": qty,
                    "entry_tl": amount_tl,
                    "entry_time": datetime.now().isoformat(),
                    "max_price": price
                }
                state['max_price'] = price
                print(f"[AL] {price:.2f} TL - {qty:.6f} BTC")
                if user_chat_id:
                    send_telegram(user_chat_id, f"🟢 *AL* {price:.2f} TL - {amount_tl:.2f} TL'lik alim")
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

                print(f"[TAKIP] Kar %{pnl_percent:.2f} | Max %{max_pnl:.2f} | Zirveden -%{drop_from_max:.3f}")

                should_sell = False
                reason = ""

                if max_pnl >= profit_trigger:
                    if drop_from_max >= trailing_drop:
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
                    commission = (entry_tl + exit_tl) * 0.001
                    pnl_tl = exit_tl - entry_tl - commission
                    
                    state['balance'] += pnl_tl
                    state['daily_count'] += 1

                    trade = {
                        "entry": entry,
                        "exit": price,
                        "max": max_p,
                        "pnl_percent": pnl_percent,
                        "pnl": pnl_tl,
                        "commission": commission,
                        "reason": reason,
                        "time": datetime.now().isoformat(),
                        "test": TEST_MODE
                    }
                    engine.add_trade(trade)
                    
                    print(f"[SAT] {reason} | {pnl_tl:.2f} TL")
                    if user_chat_id:
                        send_telegram(user_chat_id, f"🔴 *SAT* {reason}\nKar: {pnl_tl:.2f} TL\nBakiye: {state['balance']:.2f} TL")
                    
                    state['position'] = None
                    state['max_price'] = 0
                    save_json(STATE_FILE, state)

            time.sleep(20)

        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=telegram_polling, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
