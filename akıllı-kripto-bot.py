"""
AKILLI KRIPTO BOT - TEST MODU
Bütçe: 5000 TL, %25 ile girer, %3 kar sonrası %0.8 trailing ile kapatır
Günlük 200 işlem limiti, kendini geliştiren sistem
Render'da 7/24 çalışır, para çekme yetkisi YOK
"""
import os
import time
import json
import math
import threading
from datetime import datetime, date
from flask import Flask
import requests

# --- AYARLAR ---
BUDGET_TL = 5000.0
USE_PERCENT = 0.25  # kasanın %25'i
DAILY_LIMIT = 200
PROFIT_TRIGGER = 3.0  # %3 üstü takibe al
TRAILING_DROP = 0.8   # zirveden %0.8 düşünce kapat

TEST_MODE = os.getenv("TEST_MODE", "True") == "True"
BOT_TOKEN = os.getenv("BOT_TOKEN", os.getenv("TELEGRAM_TOKEN", "8926612773:AAE-7procFjj4PpqxbzUyy0Xv1b26W0kPeY"))
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")

# Dosyalar
TRADE_LOG = "trade_history.json"
STATE_FILE = "bot_state.json"

app = Flask(__name__)

@app.route('/')
def home():
    return f"BOT AKTIF - TEST_MODE={TEST_MODE} - {datetime.now()}"

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_btc_price_tl():
    """Binance TR BTC/TRY fiyatı, olmazsa CoinGecko"""
    try:
        # Binance TR ticker
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

def send_telegram(text):
    if not BOT_TOKEN:
        return
    try:
        # senin chat id'ni bulmak için botu ilk mesaj atan kişi
        # burayı basit tuttuk - log dosyasına yazıyoruz, borsa botunla aynı token
        print(f"[TELEGRAM] {text}")
        # Telegram API - tüm güncel sohbetlere gönderim için borsa botunun kullandığı yöntem
        # requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":"YOUR_CHAT_ID","text":text})
    except Exception as e:
        print(f"Telegram hata: {e}")

class SelfLearningEngine:
    """Kendini geliştiren motor - geçmiş işlemlerden parametre optimize eder"""
    def __init__(self):
        self.history = load_json(TRADE_LOG, [])

    def add_trade(self, trade):
        self.history.append(trade)
        # son 500 işlemi tut
        self.history = self.history[-500:]
        save_json(TRADE_LOG, self.history)

    def get_optimized_params(self):
        """Son 50 işlemin win rate'ine göre trailing ayarla"""
        if len(self.history) < 20:
            return PROFIT_TRIGGER, TRAILING_DROP
        
        recent = self.history[-50:]
        wins = [t for t in recent if t['pnl'] > 0]
        win_rate = len(wins) / len(recent) * 100
        
        # Eğer win rate düşükse trailing'i biraz genişlet, yüksekse daralt
        if win_rate < 45:
            # çok erken satıyoruz, biraz daha tolerans ver
            new_trailing = min(1.5, TRAILING_DROP + 0.1)
        elif win_rate > 65:
            # çok bekletiyoruz, biraz daha sıkı sat
            new_trailing = max(0.4, TRAILING_DROP - 0.1)
        else:
            new_trailing = TRAILING_DROP
        
        print(f"[LEARNING] WinRate %{win_rate:.1f} - Trailing %{new_trailing:.2f} olarak ayarlandı")
        return PROFIT_TRIGGER, new_trailing

    def stats(self):
        if not self.history:
            return "Henüz işlem yok"
        total = len(self.history)
        wins = len([t for t in self.history if t['pnl'] > 0])
        total_pnl = sum(t['pnl'] for t in self.history)
        total_comm = sum(t['commission'] for t in self.history)
        return f"Toplam: {total} | Kazanan: {wins} (%{wins/total*100:.1f}) | Net Kar: {total_pnl:.2f} TL | Komisyon: {total_comm:.2f} TL"

engine = SelfLearningEngine()

def trading_loop():
    print(f"BOT BAŞLADI - TEST_MODE={TEST_MODE} - Bütçe {BUDGET_TL} TL")
    state = load_json(STATE_FILE, {"daily_count":0, "last_date":str(date.today()), "balance":BUDGET_TL, "position":None, "max_price":0})
    
    while True:
        try:
            # Gün yenileme
            today_str = str(date.today())
            if state['last_date'] != today_str:
                state['daily_count'] = 0
                state['last_date'] = today_str
                save_json(STATE_FILE, state)
                send_telegram(f"Yeni gün {today_str} - Limit sıfırlandı")

            if state['daily_count'] >= DAILY_LIMIT:
                print(f"Günlük limit {DAILY_LIMIT} doldu, uyuyorum...")
                time.sleep(3600)
                continue

            price = get_btc_price_tl()
            if price is None:
                print("Fiyat alınamadı, 10sn bekle")
                time.sleep(10)
                continue

            profit_trigger, trailing_drop = engine.get_optimized_params()

            # POZİSYON YOKSA AL
            if state['position'] is None:
                # Basit giriş stratejisi: Her saat başı test için al (gerçekte RSI/MACD eklenecek)
                # Şimdilik her döngüde rastgele değil, fiyat düştüyse al mantığı
                # TEST modunda her zaman alım denemesi
                amount_tl = state['balance'] * USE_PERCENT
                if amount_tl < 100:
                    print("Bakiye çok düşük")
                    time.sleep(60)
                    continue
                
                qty = amount_tl / price
                commission = amount_tl * 0.001  # %0.1 komisyon
                
                state['position'] = {
                    "entry_price": price,
                    "qty": qty,
                    "entry_tl": amount_tl,
                    "entry_time": datetime.now().isoformat(),
                    "max_price": price
                }
                state['max_price'] = price
                print(f"[AL] {price:.2f} TL - {qty:.6f} BTC - {amount_tl:.2f} TL - Komisyon {commission:.2f}")
                save_json(STATE_FILE, state)
            
            else:
                # POZİSYON VARSA TAKİP ET
                entry = state['position']['entry_price']
                max_p = state['position']['max_price']
                
                if price > max_p:
                    state['position']['max_price'] = price
                    max_p = price
                
                pnl_percent = (price - entry) / entry * 100
                max_pnl = (max_p - entry) / entry * 100
                drop_from_max = (max_p - price) / max_p * 100

                print(f"[TAKIP] Giriş {entry:.2f} | Şimdi {price:.2f} | Kar %{pnl_percent:.2f} | Max %{max_pnl:.2f} | Zirveden -%{drop_from_max:.3f}")

                should_sell = False
                reason = ""

                if max_pnl >= profit_trigger:
                    # Kar %3'ü geçti, trailing aktif
                    if drop_from_max >= trailing_drop:
                        should_sell = True
                        reason = f"Trailing Stop - Zirve {max_p:.2f} TL'den %{drop_from_max:.2f} düştü (Tetik %{profit_trigger} / Trailing %{trailing_drop})"
                else:
                    # Stop-loss %2.5 zararda kapat (güvenlik)
                    if pnl_percent <= -2.5:
                        should_sell = True
                        reason = f"Stop-Loss %{pnl_percent:.2f}"

                if should_sell:
                    qty = state['position']['qty']
                    exit_tl = qty * price
                    entry_tl = state['position']['entry_tl']
                    commission = (entry_tl + exit_tl) * 0.001
                    pnl_tl = exit_tl - entry_tl - commission
                    
                    state['balance'] += pnl_tl  # Kar/zararı bakiyeye ekle
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
                    
                    print(f"[SAT] {reason} | Kar {pnl_tl:.2f} TL | Bakiye {state['balance']:.2f} TL")
                    
                    state['position'] = None
                    state['max_price'] = 0
                    save_json(STATE_FILE, state)

            time.sleep(20)  # 20 saniyede bir kontrol

        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Flask web server (Render için gerekli - port dinlemezse kapanır)
    threading.Thread(target=trading_loop, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
