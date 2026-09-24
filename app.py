"""
AKILLI KRIPTO BOT - EKRANLI VERSIYON
/ linkine girince dashboard gorunur
"""
import os
import time
import json
import threading
from datetime import datetime, date
from flask import Flask
import requests

BUDGET_TL = 5000.0
USE_PERCENT = 0.25
DAILY_LIMIT = 200
PROFIT_TRIGGER = 1.0  # HIZLI TEST ICIN %1 yaptik
TRAILING_DROP = 0.3   # HIZLI TEST ICIN %0.3 yaptik

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
            json.dump(data, f, indent=2, ensure_ascii=False)
    except:
        pass

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

# --- DASHBOARD HTML ---
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
        pos_html = f"""
        <div style="background:#1e3a2e;color:#4ade80;padding:15px;border-radius:10px;margin:10px 0">
            <b>📈 POZISYONDA</b><br>
            Giriş: {entry:,.2f} TL<br>
            Şimdi: {price:,.2f} TL<br>
            Max: {max_p:,.2f} TL<br>
            Kar: %{pnl:.3f}<br>
            Zirveden düşüş: %{drop:.3f}
        </div>
        """
    else:
        pos_html = f"""<div style="background:#3a3a1e;color:#facc15;padding:15px;border-radius:10px;margin:10px 0">Pozisyon YOK - Alım bekleniyor - Fiyat: {price:,.2f} TL</div>""" if price else "<div>Fiyat alınamadı</div>"

    # son 10 işlem
    trades_html = ""
    for t in reversed(history[-10:]):
        color = "#4ade80" if t['pnl'] > 0 else "#f87171"
        trades_html += f"<div style='border-bottom:1px solid #333;padding:8px;display:flex;justify-content:space-between'><span>{t['time'][11:19]} - {t['reason']}</span><span style='color:{color}'>{t['pnl']:.2f} TL (%{t['pnl_percent']:.2f})</span></div>"
    if not trades_html:
        trades_html = "<div style='padding:10px;color:#888'>Henüz işlem yok</div>"

    total_pnl = sum(t['pnl'] for t in history)
    win = len([t for t in history if t['pnl']>0])
    total = len(history)

    html = f"""
    <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="refresh" content="10">
    <title>Akıllı Kripto Bot</title>
    <style>body{{font-family:system-ui;background:#0f0f0f;color:#eee;margin:0;padding:15px}} .card{{background:#1a1a1a;border-radius:12px;padding:15px;margin:10px 0;border:1px solid #333}} h1{{font-size:20px}} .big{{font-size:28px;font-weight:bold}}</style>
    </head><body>
    <h1>🚀 Akıllı Kripto Bot - CANLI PANEL</h1>
    <div style="color:#888">Otomatik yenilenir (10 sn) - {datetime.now().strftime('%H:%M:%S')}</div>
    
    <div class="card">
        <div>Bakiye</div><div class="big">{state.get('balance',BUDGET_TL):,.2f} TL</div>
        <div style="display:flex;gap:20px;margin-top:10px">
            <div>Toplam Kar: <b style="color:{'#4ade80' if total_pnl>=0 else '#f87171'}">{total_pnl:.2f} TL</b></div>
            <div>İşlem: {total} | Kazanan: {win}</div>
            <div>Günlük: {state.get('daily_count',0)}/{DAILY_LIMIT}</div>
        </div>
        <div style="margin-top:8px;color:#888">Mod: {'TEST - Sanal' if TEST_MODE else 'LIVE'} | Tetik: %{PROFIT_TRIGGER} | Trailing: %{TRAILING_DROP}</div>
    </div>

    {pos_html}

    <div class="card">
        <b>📜 Son İşlemler</b>
        {trades_html}
    </div>

    <div class="card" style="color:#888;font-size:13px">
        Bot link: https://akilli-kripto-bot.onrender.com<br>
        Telegram: @kemal_borsa_bot - Komutlar: /start /durum /bakiye /fiyat
    </div>
    </body></html>
    """
    return html

# --- TELEGRAM POLLING ---
last_update_id = 0
user_chat_id = None

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
                time.sleep(5)
                continue
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                last_update_id = upd["update_id"]
                msg = upd.get("message")
                if not msg: continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text","").strip()
                user_chat_id = chat_id
                state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
                price = get_btc_price_tl()
                if text == "/start":
                    send_telegram(chat_id, f"🚀 *Akilli Kripto Bot Aktif!*\n\nBakiye: {state['balance']:.2f} TL\nPanel: https://akilli-kripto-bot.onrender.com\n\nKomutlar:\n/durum\n/bakiye\n/fiyat")
                elif text == "/durum":
                    pos = state.get("position")
                    if pos:
                        pnl = (price - pos['entry_price'])/pos['entry_price']*100 if price else 0
                        send_telegram(chat_id, f"📊 Fiyat: {price:.2f} TL\nGiris: {pos['entry_price']:.2f} TL\nKar: %{pnl:.2f}\nBakiye: {state['balance']:.2f}")
                    else:
                        send_telegram(chat_id, f"📊 Fiyat: {price:.2f} TL\nPozisyon: YOK\nBakiye: {state['balance']:.2f}")
                elif text == "/bakiye":
                    send_telegram(chat_id, f"💰 Bakiye: {state['balance']:.2f} TL")
                elif text == "/fiyat":
                    send_telegram(chat_id, f"₿ {price:.2f} TL" if price else "Fiyat yok")
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
        return PROFIT_TRIGGER, TRAILING_DROP

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
                state['position'] = {"entry_price": price, "qty": qty, "entry_tl": amount_tl, "entry_time": datetime.now().isoformat(), "max_price": price}
                state['max_price'] = price
                print(f"[AL] {price:.2f}")
                if user_chat_id:
                    send_telegram(user_chat_id, f"🟢 AL {price:.2f} TL - {amount_tl:.2f} TL")
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
                print(f"[TAKIP] %{pnl_percent:.2f} | Max %{max_pnl:.2f} | -%{drop_from_max:.3f}")
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
                    pnl_tl = exit_tl - entry_tl - (entry_tl+exit_tl)*0.001
                    state['balance'] += pnl_tl
                    state['daily_count'] += 1
                    trade = {"entry": entry, "exit": price, "max": max_p, "pnl_percent": pnl_percent, "pnl": pnl_tl, "commission": (entry_tl+exit_tl)*0.001, "reason": reason, "time": datetime.now().isoformat(), "test": TEST_MODE}
                    engine.add_trade(trade)
                    print(f"[SAT] {reason} | {pnl_tl:.2f}")
                    if user_chat_id:
                        send_telegram(user_chat_id, f"🔴 SAT {reason}\nKar: {pnl_tl:.2f} TL\nBakiye: {state['balance']:.2f}")
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
