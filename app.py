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
    except Exception as e:
        print(f"load_json hata: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"save_json hata: {e}")

def get_btc_price_tl():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCTRY", timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except Exception as e:
        print(f"Binance hata: {e}")
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=try", timeout=10)
        return float(r.json()['bitcoin']['try'])
    except Exception as e:
        print(f"Coingecko hata: {e}")
        return None

def send_telegram(chat_id, text):
    if not BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram hata: {e}")

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
        pos_html = f"""<div style="background:#1e3a2e;color:#4ade80;padding:15px;border-radius:10px;margin:10px 0"><b>📈 POZİSYONDA</b><br>Giriş: {entry:,.2f} TL<br>Şimdi: {price:,.2f} TL<br>Max: {max_p:,.2f} TL<br>Kar: %{pnl:.3f}<br>Zirveden düşüş: %{drop:.3f}</div>"""
    else:
        pos_html = f"""<div style="background:#3a3a1e;color:#facc15;padding:15px;border-radius:10px;margin:10px 0">Pozisyon YOK - Alım bekleniyor - Fiyat: {price:,.2f} TL</div>""" if price else "<div>Fiyat alınamadı</div>"
    trades_html = ""
    for t in reversed(history[-10:]):
        color = "#4ade80" if t['pnl'] > 0 else "#f87171"
        trades_html += f"<div style='border-bottom:1px solid #333;padding:8px;display:flex;justify-content:space-between'><span>{t['time'][11:19]} - {t['reason']}</span><span style='color:{color}'>{t['pnl']:.2f} TL (%{t['pnl_percent']:.2f})</span></div>"
    if not trades_html:
        trades_html = "<div style='padding:10px;color:#888'>Henüz işlem yok</div>"
    total_pnl = sum(t['pnl'] for t in history)
    win = len([t for t in history if t['pnl']>0])
    total = len(history)
    html = f"""<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="10"><title>Akıllı Kripto Bot</title><style>body{{font-family:system-ui;background:#0f0f0f;color:#eee;margin:0;padding:15px}} .card{{background:#1a1a1a;border-radius:12px;padding:15px;margin:10px 0;border:1px solid #333}} h1{{font-size:20px}} .big{{font-size:28px;font-weight:bold}}</style></head><body><h1>🚀 Akıllı Kripto Bot - CANLI PANEL</h1><div style="color:#888">Otomatik yenilenir (10 sn) - {datetime.now().strftime('%H:%M:%S')}</div><div class="card"><div>Bakiye</div><div class="big">{state.get('balance',BUDGET_TL):,.2f} TL</div><div style="display:flex;gap:20px;margin-top:10px"><div>Toplam Kar: <b style="color:{'#4ade80' if total_pnl>=0 else '#f87171'}">{total_pnl:.2f} TL</b></div><div>İşlem: {total} | Kazanan: {win}</div><div>Günlük: {state.get('daily_count',0)}/{DAILY_LIMIT}</div></div><div style="margin-top:8px;color:#888">Mod: {'TEST - Sanal' if TEST_MODE else 'LIVE'} | Tetik: %{PROFIT_TRIGGER} | Trailing: %{TRAILING_DROP}</div></div>{pos_html}<div class="card"><b>📜 Son İşlemler</b>{trades_html}</div><div class="card"><a href="/force-buy" style="background:#4ade80;color:#000;padding:10px 15px;border-radius:8px;text-decoration:none;display:inline-block;margin-right:10px">🟢 Zorla AL</a><a href="/force-sell" style="background:#f87171;color:#000;padding:10px 15px;border-radius:8px;text-decoration:none;display:inline-block">🔴 Zorla SAT</a></div><div class="card" style="color:#888;font-size:13px">Bot link: https://akilli-kripto-bot.onrender.com<br>Telegram: @kemal_borsa_bot - Komutlar: /start /durum /bakiye /fiyat</div></body></html>"""
    return html

@app.route('/force-buy')
def force_buy():
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    price = get_btc_price_tl()
    if not price:
        return "Fiyat alınamadı, 10 sn sonra tekrar dene"
    if state.get("position"):
        return f"Zaten pozisyondasın! Giriş: {state['position']['entry_price']}"
    amount_tl = state['balance'] * USE_PERCENT
    qty = amount_tl / price
    state['position'] = {"entry_price": price, "qty": qty, "entry_tl": amount_tl, "entry_time": datetime.now().isoformat(), "max_price": price}
    state['max_price'] = price
    save_json(STATE_FILE, state)
    print(f"[FORCE AL] {price:.2f} TL - {qty:.6f} BTC")
    return f"ALIM YAPILDI: {price:.2f} TL - <a href='/'>Panele dön</a>"

@app.route('/force-sell'
