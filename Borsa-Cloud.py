"""
Borsa Bot v5 - CLOUD 7/24 - Render.com icin
"""
import os, threading, yfinance as yf, pandas as pd
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio, logging

TOKEN = os.getenv("BOT_TOKEN", "8926612773:AAE-7procFjj4PpqxbzUyy0Xv1b26W0kPeY")
WATCHLIST = ["OTKAR.IS", "FROTO.IS", "INDES.IS", "BKRGY.IS", "SASA.IS", "HLGYO.IS", "VESBE.IS"]
TICKER_MAP = {"OTOKAR":"OTKAR","OTOKR":"OTKAR","FORD":"FROTO"}

logging.basicConfig(level=logging.WARNING)

# --- Flask keep-alive (Render port icin) ---
app_flask = Flask(__name__)
@app_flask.route("/")
def home():
    return "kemal_borsa_bot aktif! t.me/kemal_borsa_bot"

def run_flask():
    app_flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- Borsa Analiz ---
def duzelt(kod):
    kod=kod.upper().replace(".IS","").strip()
    return f"{TICKER_MAP.get(kod,kod)}.IS"

def analiz(kod_raw):
    kod=duzelt(kod_raw)
    try:
        ticker=yf.Ticker(kod)
        data=ticker.history(period="1y", auto_adjust=True)
        if data.empty or len(data)<30:
            data=yf.download(kod, period="1y", interval="1d", progress=False, auto_adjust=True)
        if data.empty or len(data)<30:
            return None, f"{kod.replace('.IS','')} icin veri yok"
        close=data['Close']
        if isinstance(close, pd.DataFrame): close=close.iloc[:,0]
        close=pd.Series(close).dropna()
        delta=close.diff()
        gain=delta.where(delta>0,0).rolling(14).mean()
        loss=(-delta.where(delta<0,0)).rolling(14).mean()
        rsi=100-(100/(1+gain/loss))
        son_rsi=float(rsi.iloc[-1]); son=float(close.iloc[-1])
        exp12=close.ewm(12).mean(); exp26=close.ewm(26).mean()
        macd=exp12-exp26; sig=macd.ewm(9).mean()
        trend="YUKARI 📈" if macd.iloc[-1]>sig.iloc[-1] else "ASAGI 📉"
        destek=float(data['Low'].tail(20).min()); direnc=float(data['High'].tail(20).max())
        if son_rsi<30: sinyal="AL FIRSATI 🟢"
        elif son_rsi>70: sinyal="SAT SINYALI 🔴"
        elif son_rsi>50 and "YUKARI" in trend: sinyal="YUKSELIS TRENDI 🔵"
        else: sinyal="BEKLE / NOTR ⚪"
        msg=(f"*{kod.replace('.IS','')}* - {datetime.now().strftime('%d.%m %H:%M')}\n"
             f"💰 Fiyat: *{son:.2f} TL*\n"
             f"📊 RSI: *{son_rsi:.1f}* | MACD: {trend}\n"
             f"🚦 Sinyal: *{sinyal}*\n"
             f"🛡️ Destek: {destek:.2f} | Direnc: {direnc:.2f}")
        return msg, None
    except Exception as e: return None, f"Hata: {e}"

async def start(update, context):
    await update.message.reply_text("Merhaba! Borsa Asistan v5 CLOUD 7/24 aktif ✅\n\n/hisse OTKAR\n/hisse FROTO\n/izle\n/help", parse_mode="Markdown")

async def hisse(update, context):
    if not context.args: await update.message.reply_text("Kullanim: /hisse OTKAR"); return
    kod=context.args[0]
    await update.message.reply_text(f"🔍 {kod} analiz...")
    m,h=analiz(kod)
    await update.message.reply_text(m if m else f"❌ {h}", parse_mode="Markdown")

async def izle(update, context):
    await update.message.reply_text(f"📡 {len(WATCHLIST)} hisse taraniyor...")
    for hk in WATCHLIST:
        m,h=analiz(hk)
        if m: await update.message.reply_text(m, parse_mode="Markdown"); await asyncio.sleep(1)

async def helpc(update, context):
    await update.message.reply_text("/start\n/hisse OTKAR\n/izle\n/help", parse_mode="Markdown")

async def unknown(update, context):
    await update.message.reply_text("❓ /help yaz. Ornek: /hisse OTKAR")

def run_bot():
    print("=== kemal_borsa_bot CLOUD ===")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hisse", hisse))
    app.add_handler(CommandHandler("izle", izle))
    app.add_handler(CommandHandler("help", helpc))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.run_polling()

if __name__=="__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
