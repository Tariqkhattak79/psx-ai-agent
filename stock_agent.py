import pandas as pd
import json
import os
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import requests
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pypsx_toolkit as pt
import warnings

warnings.filterwarnings("ignore")
load_dotenv()

GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET")
USER_ID = os.getenv("PSX_USER_ID", "default_user")

if SUPABASE_URL:
    SUPABASE_URL = SUPABASE_URL.strip().rstrip("/")

def calc_rsi(data, period=14):
    delta = data["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rs = gain.rolling(period).mean() / loss.rolling(period).mean()
    return 100 - (100 / (1 + rs))

def calc_atr(data, period=14):
    tr = data["High"] - data["Low"]
    return tr.rolling(period).mean()

def calc_volume_status(current_vol, avg_vol):
    if current_vol > avg_vol * 2: return "VOLUME SPIKE"
    elif current_vol > avg_vol * 1.2: return "HIGH VOLUME"
    elif current_vol < avg_vol * 0.8: return "LOW VOLUME"
    return "NORMAL VOLUME"

def calc_breakout(latest_close, highest_20, current_vol, avg_vol):
    dist = ((latest_close / highest_20) - 1) * 100
    if dist > 5 and current_vol > avg_vol * 2: return "EXPLOSIVE BREAKOUT", 100, True
    elif dist > 2 and current_vol > avg_vol * 1.5: return "STRONG BREAKOUT", 80, True
    elif dist > 0: return "MEDIUM BREAKOUT", 60, True
    elif latest_close > highest_20 * 0.98: return "NEAR BREAKOUT", 40, False
    return "NO BREAKOUT", 0, False

def calc_divergence(data, is_bullish=True):
    try:
        recent_price = data["Close"].tail(14)
        recent_rsi = data["RSI"].tail(14)
        if is_bullish:
            p_old, p_new = recent_price.iloc[:7].min(), recent_price.iloc[7:].min()
            r_old, r_new = recent_rsi.iloc[:7].min(), recent_rsi.iloc[7:].min()
            if p_new < p_old and r_new > r_old: return "YES"
        else:
            p_old, p_new = recent_price.iloc[:7].max(), recent_price.iloc[7:].max()
            r_old, r_new = recent_rsi.iloc[:7].max(), recent_rsi.iloc[7:].max()
            if p_new > p_old and r_new < r_old: return "YES"
    except: pass
    return "NO"

def calc_patterns(data, current_vol, avg_vol, rsi, ma20):
    latest, previous = data.iloc[-1], data.iloc[-2]
    bull_engulf = (previous["Close"] < previous["Open"] and latest["Close"] > latest["Open"] and latest["Close"] > previous["Open"] and latest["Open"] < previous["Close"])
    bear_engulf = (previous["Close"] > previous["Open"] and latest["Close"] < latest["Open"] and latest["Open"] > previous["Close"] and latest["Close"] < previous["Open"])
    accum = (current_vol > avg_vol * 1.2 and 45 < rsi < 65 and latest["Close"] > ma20)
    distrib = (current_vol > avg_vol and latest["Close"] < ma20)
    return bull_engulf, bear_engulf, accum, distrib

def fetch_one(symbol):
    data = None
    live_price = None
    try:
        df = pt.download(symbol, period="400d", show_progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(-1)
            df = df.reset_index()
            df.columns = [str(c).lower() for c in df.columns]
            if "date" in df.columns: df = df.rename(columns={"date": "Date"})
            elif "datetime" in df.columns: df = df.rename(columns={"datetime": "Date"})
            elif "index" in df.columns: df = df.rename(columns={"index": "Date"})
            df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.sort_values("Date").set_index("Date")
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            data = df[["Open", "High", "Low", "Close", "Volume"]]
            if not data.empty:
                live_price = float(data["Close"].iloc[-1])
    except Exception:
        pass
    return symbol, data, live_price

def calculate_position_size(row, current_portfolio, risk_per_trade, max_position_pkr):
    entry, stop = row["Close"], row["StopLoss"]
    if entry is None or stop is None or entry <= stop: return (0, 0, "NO DATA")
    risk_per_share = entry - stop
    if risk_per_share <= 0: return (0, 0, "INVALID STOP")
    shares = int(risk_per_trade / risk_per_share)
    max_shares = int(max_position_pkr / entry)
    if shares > max_shares: shares, capped = max_shares, True
    else: capped = False
    if shares < 1: return (0, 0, "TOO SMALL")
    actual_risk = shares * risk_per_share
    held = row["Symbol"] in current_portfolio
    if held:
        held_buy = current_portfolio[row["Symbol"]]["BuyPrice"]
        if row.get("LivePrice", entry) <= held_buy * 0.90: return (0, round(actual_risk, 2), "EXIT - LOSS LIMIT")
        if row.get("LivePrice", entry) < held_buy and row["Signal"] in ["BUY", "STRONG BUY"]: return (shares, round(actual_risk, 2), f"ADD {shares} SHARES")
        return (0, 0, "HOLD")
    if row["Signal"] in ["BUY", "STRONG BUY"]:
        suffix = " (capped)" if capped else ""
        return (shares, round(actual_risk, 2), f"BUY {shares} SHARES{suffix}")
    return (0, 0, "AVOID")

def upload_to_supabase(actions_data, report_data):
    if not SUPABASE_URL or not SUPABASE_SECRET: return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/signals"
        headers = {"apikey": SUPABASE_SECRET, "Authorization": f"Bearer {SUPABASE_SECRET}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}
        payload = {"user_id": USER_ID, "data": {"generated": actions_data.get("generated"), "actions": actions_data, "report": report_data}}
        return requests.post(url, headers=headers, json=payload).status_code in [200, 201]
    except: return False

def fetch_from_supabase():
    if not SUPABASE_URL or not SUPABASE_SECRET: return {}
    try:
        url = f"{SUPABASE_URL}/rest/v1/signals?user_id=eq.{USER_ID}&select=data"
        headers = {"apikey": SUPABASE_SECRET, "Authorization": f"Bearer {SUPABASE_SECRET}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0: return data[0]["data"]
    except: pass
    return {}

def main():
    print("Starting PSX AI Agent...")
    _sd = fetch_from_supabase()
    _sb_portfolio = _sd.get("portfolio") if isinstance(_sd, dict) else None
    
    if isinstance(_sb_portfolio, list) and len(_sb_portfolio) > 0:
        portfolio = pd.DataFrame([{
            "Symbol": str(p.get("Symbol", "")).strip().upper(),
            "Shares": float(p.get("Shares", 0)),
            "BuyPrice": float(p.get("BuyPrice", 0)),
            "TargetPrice": float(p.get("TargetPrice", 0))
        } for p in _sb_portfolio])
    else:
        portfolio = pd.read_csv("portfolio.csv")

    TOTAL_INVESTMENT = float((portfolio["Shares"] * portfolio["BuyPrice"]).sum()) if len(portfolio) > 0 else 0.0
    RISK_PER_TRADE = TOTAL_INVESTMENT * 0.01
    MAX_POSITION_PKR = TOTAL_INVESTMENT * 0.10
    current_portfolio_map = {r["Symbol"]: {"Shares": float(r["Shares"]), "BuyPrice": float(r["BuyPrice"])} for _, r in portfolio.iterrows()}

    symbols = pd.read_csv("symbols.csv")["Symbol"].tolist()
    print(f"Fetching {len(symbols)} symbols...")
    FETCH_CACHE = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_one, s): s for s in symbols}
        for fut in as_completed(futures):
            sym, d, lp = fut.result()
            FETCH_CACHE[sym] = (d, lp)
    
    valid_count = sum(1 for s, (d, lp) in FETCH_CACHE.items() if d is not None)
    print(f"Fetch done ({len(FETCH_CACHE)}/{len(symbols)}) - {valid_count} valid.")

    results = []
    for symbol, (data, live_price) in FETCH_CACHE.items():
        if data is None or len(data) < 50: continue
        
        data["MA20"] = data["Close"].rolling(20).mean()
        data["MA50"] = data["Close"].rolling(50).mean()
        data["RSI"] = calc_rsi(data)
        data["ATR"] = calc_atr(data)
        
        latest = data.iloc[-1]
        rsi = latest["RSI"]
        atr = latest["ATR"]
        avg_vol = data["Volume"].rolling(20).mean().iloc[-1]
        curr_vol = latest["Volume"]
        highest_20 = data["High"].tail(20).max()
        support_5d = data["Low"].tail(5).min()
        res_10d = data["High"].tail(10).max()
        
        vol_status = calc_volume_status(curr_vol, avg_vol)
        breakout_status, breakout_strength, is_breakout = calc_breakout(latest["Close"], highest_20, curr_vol, avg_vol)
        bull_div = calc_divergence(data, True)
        bear_div = calc_divergence(data, False)
        bull_engulf, bear_engulf, accum, distrib = calc_patterns(data, curr_vol, avg_vol, rsi, latest["MA20"])
        
        score = 0
        if latest["Close"] > latest["MA20"]: score += 1
        if latest["MA20"] > latest["MA50"]: score += 1
        if curr_vol > avg_vol: score += 1
        if is_breakout: score += 1
        if accum: score += 1
        if distrib: score -= 1
        if bull_div == "YES": score += 1
        if bear_div == "YES": score -= 1
        
        signal = "STRONG BUY" if score >= 4 and rsi < 65 else "BUY" if score >= 2 and rsi < 70 else "SELL" if score <= -1 else "HOLD"
        
        buy_price = round(latest["Close"], 2)
        stop_1 = support_5d * 0.98
        stop_2 = buy_price - (atr * 1.5)
        stop_loss = round(max(stop_1, stop_2) * 0.97, 2)
        target1 = round(buy_price + (atr * 3), 2)
        target2 = round(buy_price + (atr * 5), 2)
        
        results.append({
            "Symbol": symbol, "Close": buy_price, "LivePrice": live_price,
            "RSI": round(rsi, 2), "Signal": signal, "Score": score,
            "VolumeStatus": vol_status, "BreakoutStatus": breakout_status,
            "BullishDivergence": bull_div, "BearishDivergence": bear_div,
            "Pattern": "Bullish Engulfing" if bull_engulf else "Distribution" if distrib else "",
            "StopLoss": stop_loss, "Target1": target1, "Target2": target2,
            "Support5d": support_5d, "Resistance10d": res_10d
        })

    df = pd.DataFrame(results)
    if df.empty:
        print("No data processed.")
        return

    sizes = df.apply(lambda row: calculate_position_size(row, current_portfolio_map, RISK_PER_TRADE, MAX_POSITION_PKR), axis=1)
    df["PositionSize"] = [s[0] for s in sizes]
    df["PositionRiskPKR"] = [s[1] for s in sizes]
    df["PositionAction"] = [s[2] for s in sizes]
    df["MasterScore"] = (df["Score"] * 10).clip(0, 100)
    df = df.sort_values("MasterScore", ascending=False)

    df.to_excel("psx_report.xlsx", index=False)
    df.to_json("psx_report.json", orient="records", indent=4)
    
    actions_payload = {
        "generated": datetime.now().isoformat(),
        "buy_now": [],
        "ready": [],
        "wait": [],
        "exit": [],
        "watch": [],
        "portfolio": [],
        "portfolio_holdings": [],
        "report": results
    }
    with open("psx_actions.json", "w") as f:
        json.dump(actions_payload, f, indent=4)
        
    print("Reports and Actions saved.")

    now = datetime.now()
    if (now.hour == 15 and now.minute >= 30) or (now.hour == 15 and now.minute <= 45):
        print("Sending email...")
    else:
        print("Skipping email (waiting for 3:30 PM).")

if __name__ == "__main__":
    main()
