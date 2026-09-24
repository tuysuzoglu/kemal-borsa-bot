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
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"save hata {e}")

def get_btc_price_tl():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCTRY", timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    try:
        r1 = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        r2 = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY", timeout=5)
        if r1.status_code == 200 and r2.status_code == 200:
            return float(r1.json()['price']) * float(r2.json()['price'])
    except:
        pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=try", timeout=8)
        if r.status_code == 200:
            return float(r.json()['bitcoin']['try'])
    except:
        pass
    return 4065000.0

def send_telegram(chat_id, text):
    if not BOT_TOKEN or not chat_id:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

@app.route('/')
def home():
    state = load_json(STATE_FILE, {"balance": BUDGET_TL, "daily_count": 0, "last_date": str(date.today()), "position": None})
    history = load_json(TRADE_LOG, [])
    price = get_btc_price_tl()
    pos = state.get("position")
    if pos and price:
        entry = pos['entry_price']
        pnl = (price - entry) / entry * 100 if entry else 0
        max_p = pos.get('max_price', entry)
        drop = (max_p - price) / max_p * 100 if max_p else 0
        pos_html = f'<div style="background:#1e3a2e;color:#4ade80;padding:15px;border-radius:10px;margin:10px 0"><b>📈 POZISYONDA - CANLI</b><br>Giris: {entry:,.2f} TL<br>Simdi: {price:,.2f} TL<br>Max: {max_p:,.2f} TL<br>Kar: %{pnl:.4f}<br>Zirveden: %{drop:.4f}<br><small>Zaman: {pos.get("entry_time","")[:19]}</small></div>'
    else:
        pos_html = f'<div style="background:#3a3a1e;color:#facc15;padding:15px;border-radius:10px;margin:10px 0">Pozisyon YOK - Alim bekleniyor - Fiyat: {price:,.2f} TL</div>'
    trades_html = ""
    for t in reversed(history[-10:]):
        color = "#4ade80" if t['pnl'] > 0 else "#f87171"
        trades_html += f'<div style="border-bottom:1px solid #333;padding:8px;display:flex;justify-content:space-between"><span>{t["time"][11:19]} - {t["reason"]}</span><span style="color:{color}">{t["pnl"]:.2f} TL (%{t.get("pnl_percent",0):.2f})</span></div>'
    if not trades_html:
        trades_html = '<div style="padding:10px;color:#888">Henuz islem yok</div>'
    total_pnl = sum(t['pnl'] for t in history)
    html = f"""<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="10"><title>Bot Panel</title>
<style>body{{font-family:system-ui;background:#0f0f0f;color:#eee;margin:0;padding:15px}} .card{{background:#1a1a1a;border-radius:12px;padding:15px;margin:10px 0;border:1px solid #333}} .big{{font-size:28px;font-weight:bold}}</style>
</head><body><h1>🚀 Akilli Kripto Bot - CANLI</h1><div style="color:#888">{datetime.now().strftime('%H:%M:%S')} - 10 sn yenilenir</div>
<div class="card"><div>Bakiye</div><div class="big">{state.get('balance',BUDGET_TL):,.2f} TL</div><div>Toplam Kar: {total_pnl:.2f} | Islem: {len(history)} | Gunluk: {state.get('daily_count',0)}</div></div>
{pos_html}<div class="card"><b>Son Islemler</b>{trades_html}</div>
<div class="card"><a href="/force-buy" style="background:#4ade80;color:#000;padding:10px 15px;border-radius:8px;text-decoration:none;margin-right:10px;display:inline-block">🟢 Zorla AL</a><a href="/force-sell" style="background:#f87171;color:#000;padding:10px 15px;border-radius:8px;text-decoration:none;display:inline-block">🔴 Zorla SAT</a> <a href="/reset" style="background:#555;color:#fff;padding:10px 15px;border-radius:8px;text-decoration:none;margin-left:10px;display:inline-block">Sifirla</a></div>
</body></html>"""
    return html

@app.route('/force-buy')
def force_buy():
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    price = get_btc_price_tl()
    if state.get("position"):
        return f"Zaten pozisyondasın! Giris: {state['position']['entry_price']} <a href='/'>Panele don</a>"
    amount_tl = state['balance'] * USE_PERCENT
    qty = amount_tl / price
    state['position'] = {"entry_price": price, "qty": qty, "entry_tl": amount_tl, "entry_time": datetime.now().isoformat(), "max_price": price}
    state['last_date'] = str(date.today())
    save_json(STATE_FILE, state)
    print(f"[FORCE AL] {price:.2f} - KAYIT EDILDI", flush=True)
    time.sleep(0.5)
    # Dogrulama
    check = load_json(STATE_FILE, {})
    if check.get("position"):
        return f"ALIM YAPILDI: {price:.2f} TL - DOGRULANDI <a href='/'>Panele don</a>"
    else:
        return f"HATA: Dosya yazilmadi! {price:.2f} <a href='/'>Panele don</a>"

@app.route('/force-sell')
def force_sell():
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None})
    price = get_btc_price_tl()
    if not state.get("position"):
        return f"Pozisyon yok <a href='/'>Don</a>"
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
    return f"SATILDI: Kar {pnl_tl:.2f} TL <a href='/'>Don</a>"

@app.route('/reset')
def reset():
    save_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    save_json(TRADE_LOG, [])
    return "Sifirlandi <a href='/'>Don</a>"

last_update_id = 0
def telegram_polling():
    global last_update_id
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
            for upd in data.get("result", []):
                last_update_id = upd["update_id"]
                msg = upd.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text","").strip()
                state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None})
                price = get_btc_price_tl()
                if text == "/start":
                    send_telegram(chat_id, f"Bot Aktif! Bakiye: {state['balance']:.2f} Panel: https://akilli-kripto-bot.onrender.com")
                elif text == "/durum":
                    pos = state.get("position")
                    if pos and price:
                        pnl = (price - pos['entry_price'])/pos['entry_price']*100
                        send_telegram(chat_id, f"Fiyat: {price:.2f} Giris: {pos['entry_price']:.2f} Kar: %{pnl:.3f}")
                    else:
                        send_telegram(chat_id, f"Fiyat: {price:.2f} Pozisyon YOK")
        except Exception as e:
            print(f"Polling hata: {e}", flush=True)
            time.sleep(5)

def trading_loop():
    print(f"BOT BASLADI - TEST_MODE={TEST_MODE}", flush=True)
    while True:
        try:
            # HER SEFERINDE DOSYADAN YENIDEN OKU - FORCE-BUY'I SILMEMEK ICIN
            state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
            today_str = str(date.today())
            if state.get('last_date') != today_str:
                state['daily_count'] = 0
                state['last_date'] = today_str
                save_json(STATE_FILE, state)
            if state.get('daily_count',0) >= DAILY_LIMIT:
                print(f"Gunluk limit {DAILY_LIMIT} doldu, bekleniyor", flush=True)
                time.sleep(3600)
                continue
            price = get_btc_price_tl()
            if price is None:
                time.sleep(10)
                continue
            if state.get('position') is None:
                amount_tl = state['balance'] * USE_PERCENT
                if amount_tl < 100:
                    time.sleep(60)
                    continue
                qty = amount_tl / price
                state['position'] = {"entry_price": price, "qty": qty, "entry_tl": amount_tl, "entry_time": datetime.now().isoformat(), "max_price": price}
                print(f"[OTO AL] {price:.2f} TL - {qty:.6f} BTC", flush=True)
                save_json(STATE_FILE, state)
            else:
                entry = state['position']['entry_price']
                max_p = state['position'].get('max_price', entry)
                if price > max_p:
                    state['position']['max_price'] = price
                    max_p = price
                    save_json(STATE_FILE, state)
                pnl_percent = (price - entry) / entry * 100
                max_pnl = (max_p - entry) / entry * 100
                drop_from_max = (max_p - price) / max_p * 100 if max_p>0 else 0
                print(f"[TAKIP] Fiyat {price:.2f} Kar %{pnl_percent:.3f} Max %{max_pnl:.3f} -%{drop_from_max:.3f}", flush=True)
                should_sell = False
                reason = ""
                if max_pnl >= PROFIT_TRIGGER:
                    if drop_from_max >= TRAILING_DROP:
                        should_sell = True
                        reason = f"Trailing %{drop_from_max:.2f} (max %{max_pnl:.2f})"
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
                    state['daily_count'] = state.get('daily_count',0) + 1
                    history = load_json(TRADE_LOG, [])
                    history.append({"entry": entry, "exit": price, "max": max_p, "pnl_percent": pnl_percent, "pnl": pnl_tl, "commission": (entry_tl+exit_tl)*0.001, "reason": reason, "time": datetime.now().isoformat(), "test": TEST_MODE})
                    save_json(TRADE_LOG, history[-500:])
                    print(f"[SAT] {reason} | {pnl_tl:.2f} TL | Bakiye {state['balance']:.2f}", flush=True)
                    state['position'] = None
                    state['max_price'] = 0
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
