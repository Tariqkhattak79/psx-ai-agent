import yfinance as yf
import pandas as pd
import json
import os
import requests
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE = os.getenv("SUPABASE_PUBLISHABLE")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET")

# Ensure the URL is correct by stripping any trailing slashes or spaces
if SUPABASE_URL:
    SUPABASE_URL = SUPABASE_URL.strip().rstrip("/")


# ==================================
# PORTFOLIO CHANGE DETECTOR + TRADE LOG
# ==================================

import os
from datetime import datetime

SNAPSHOT_FILE = "portfolio_snapshot.json"
HISTORY_FILE = "portfolio_history.csv"

def detect_portfolio_changes(current_portfolio):
    """
    Compare current portfolio.csv with last snapshot.
    Append detected BUY/SELL to portfolio_history.csv.
    Returns list of new events.
    """
    events = []

    # Load last snapshot
    last = {}
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                last = json.load(f)
        except Exception:
            last = {}

    current = {}
    for _, row in current_portfolio.iterrows():
        current[row["Symbol"]] = {
            "Shares": int(row["Shares"]),
            "BuyPrice": float(row["BuyPrice"])
        }

    today = datetime.now().strftime("%Y-%m-%d")

    # Detect new positions or share increases
    for sym, data in current.items():
        old_shares = last.get(sym, {}).get("Shares", 0)

        if old_shares == 0:
            events.append({
                "Symbol": sym, "Type": "BUY",
                "Shares": data["Shares"],
                "Price": data["BuyPrice"],
                "Date": today,
                "Note": "new position"
            })
        elif data["Shares"] > old_shares:
            diff = data["Shares"] - old_shares
            events.append({
                "Symbol": sym, "Type": "BUY",
                "Shares": diff,
                "Price": data["BuyPrice"],
                "Date": today,
                "Note": "added shares"
            })
        elif data["Shares"] < old_shares:
            diff = old_shares - data["Shares"]
            events.append({
                "Symbol": sym, "Type": "SELL",
                "Shares": diff,
                "Price": data["BuyPrice"],
                "Date": today,
                "Note": "reduced shares"
            })

    # Detect fully removed positions
    for sym, old_data in last.items():
        if sym not in current:
            events.append({
                "Symbol": sym, "Type": "SELL",
                "Shares": old_data["Shares"],
                "Price": old_data["BuyPrice"],
                "Date": today,
                "Note": "position closed"
            })

    # Append events to history
    if events:
        file_exists = os.path.exists(HISTORY_FILE)

        import csv
        with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Date", "Symbol", "Type", "Shares", "Price", "Note"]
            )
            if not file_exists:
                writer.writeheader()
            for e in events:
                writer.writerow({
                    "Date": e["Date"],
                    "Symbol": e["Symbol"],
                    "Type": e["Type"],
                    "Shares": e["Shares"],
                    "Price": e["Price"],
                    "Note": e["Note"]
                })

    # Save new snapshot
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(current, f, indent=4)

    return events

# ==================================
# POSITION SIZING (Risk-Based)
# ==================================

def calculate_position_size(row, current_portfolio):
    """
    Given a stock row + current portfolio, return (shares, risk_pkr, action).
    """
    symbol = row["Symbol"]
    import math

    entry = row["Close"]
    stop = row["StopLoss"]

    # Skip rows with missing data
    if entry is None or stop is None:
        return (0, 0, "NO DATA")

    try:
        if math.isnan(float(entry)) or math.isnan(float(stop)):
            return (0, 0, "NO DATA")
    except (TypeError, ValueError):
        return (0, 0, "NO DATA")
    signal = row["Signal"]
    rsi = row["RSI"]

    if entry is None or stop is None or entry <= stop:
        return (0, 0, "NO DATA")

    risk_per_share = entry - stop

    if risk_per_share <= 0:
        return (0, 0, "INVALID STOP")


    shares = int(RISK_PER_TRADE_PKR / risk_per_share)

    if shares < 1:
        return (0, 0, "TOO SMALL")

    # Cap position at MAX_POSITION_PKR
    max_shares_by_cap = int(MAX_POSITION_PKR / entry)

    if shares > max_shares_by_cap:
        shares = max_shares_by_cap
        capped = True
    else:
        capped = False

    if shares < 1:
        return (0, 0, "TOO SMALL")

    total_cost = shares * entry
    actual_risk = shares * risk_per_share

    # Decide action
    held = symbol in current_portfolio

    if held:
        held_info = current_portfolio[symbol]
        held_buy = held_info["BuyPrice"]
        held_shares = held_info["Shares"]

        # Stop already breached on existing position?
        current_price = row.get("LivePrice") or entry
        if current_price <= held_buy * 0.90:
            return (0, round(actual_risk, 2), "EXIT — LOSS LIMIT")

        # Averaging down opportunity?
        if current_price < held_buy and signal in ["BUY", "STRONG BUY"]:
            return (shares, round(actual_risk, 2), f"ADD {shares} SHARES")

        return (0, 0, "HOLD")

    # Not held — fresh buy?
    if signal in ["BUY", "STRONG BUY"]:
        suffix = " (capped)" if capped else ""
        return (shares, round(actual_risk, 2), f"BUY {shares} SHARES{suffix}")

    return (0, 0, "AVOID")
# ==================================
# SIGNAL HISTORY LOGGER
# ==================================

SIGNAL_HISTORY_FILE = "signal_history.csv"

def log_signal_history(df_today):
    """
    Append today's signals to signal_history.csv.
    One row per (date, symbol). Replaces if already logged today.
    """
    import csv
    import os
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    # Build today's rows
    new_rows = []
    for _, r in df_today.iterrows():
        if r["Signal"] not in ("BUY", "STRONG BUY"):
            continue

        new_rows.append({
            "Date": today,
            "Symbol": r["Symbol"],
            "Signal": r["Signal"],
            "TradeStyle": r.get("TradeStyle", "-"),
            "Close": round(r["Close"], 2),
            "RSI": r["RSI"],
            "Confidence": r["Confidence"],
            "MasterScore": round(r["MasterScore"], 2),
            "StopLoss": r["StopLoss"],
            "Target1": r["Target1"],
            "BuyZone": r["BuyZoneNote"]
        })

    if not new_rows:
        return 0

    # Load existing history, drop today's old entries (avoid duplicates)
    existing = []
    if os.path.exists(SIGNAL_HISTORY_FILE):
        with open(SIGNAL_HISTORY_FILE, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            existing = [row for row in reader if row["Date"] != today]

    # Write back: old + new
    fieldnames = [
        "Date", "Symbol", "Signal", "TradeStyle", "Close",
        "RSI", "Confidence", "MasterScore", "StopLoss",
        "Target1", "BuyZone"
    ]

    with open(SIGNAL_HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing:
            writer.writerow(row)
        for row in new_rows:
            writer.writerow(row)

    return len(new_rows)
# ==================================
# PORTFOLIO VALUE HISTORY
# ==================================

VALUE_HISTORY_FILE = "portfolio_value_history.csv"

def log_portfolio_value(total_investment, total_current_value, portfolio_pl):
    """
    Append today's portfolio value to history file.
    One row per date. Replaces if already logged today.
    """
    import csv
    import os
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    new_row = {
        "Date": today,
        "Investment": round(total_investment, 2),
        "CurrentValue": round(total_current_value, 2),
        "ReturnPct": round(portfolio_pl, 2)
    }

    existing = []
    if os.path.exists(VALUE_HISTORY_FILE):
        with open(VALUE_HISTORY_FILE, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            existing = [row for row in reader if row["Date"] != today]
    fieldnames = ["Date", "Investment", "CurrentValue", "ReturnPct"]

    with open(VALUE_HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing:
            writer.writerow(row)
        writer.writerow(new_row)

# ==================================
# SUPABASE REST API UPLOAD & FETCH
# ==================================

def upload_to_supabase(user_id, actions_data, report_data):
    """
    Push today's data to Supabase using the REST API.
    """
    if not SUPABASE_URL or not SUPABASE_SECRET:
        print("⚠️  Supabase not configured — skipping upload")
        return False

    try:
        # The REST endpoint for the 'signals' table
        url = f"{SUPABASE_URL}/rest/v1/signals"

        # These headers are crucial: they tell PostgREST to merge duplicates
        headers = {
            "apikey": SUPABASE_SECRET,
            "Authorization": f"Bearer {SUPABASE_SECRET}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

        payload = {
            "user_id": user_id,
            "data": {
                "actions": actions_data,
                "report": report_data
            }
        }

        # Send the POST request to upsert the data
        response = requests.post(url, headers=headers, json=payload)

        # Check if the request was successful (status code 200 or 201)
        if response.status_code in [200, 201]:
            print(f"☁️  Uploaded to Supabase for user: {user_id}")
            return True
        else:
            print(f"⚠️  Supabase upload failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"⚠️  Supabase upload failed: {e}")
        return False


def fetch_from_supabase(user_id):
    """
    Fetch the latest signals for a given user from Supabase.
    """
    if not SUPABASE_URL or not SUPABASE_SECRET:
        print("⚠️  Supabase not configured — skipping fetch")
        return None

    try:
        # Query the 'signals' table for the specific user
        url = f"{SUPABASE_URL}/rest/v1/signals?user_id=eq.{user_id}&select=data"

        headers = {
            "apikey": SUPABASE_SECRET,
            "Authorization": f"Bearer {SUPABASE_SECRET}",
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]["data"]
            else:
                print("No data found for this user.")
                return None
        else:
            print(f"⚠️  Fetch failed: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"⚠️  Fetch failed: {e}")
        return None
def calculate_trade_stats():
    """
    Read portfolio_history.csv, match BUY→SELL per symbol,
    return dict with win rate + avg gain/loss.
    """
    import csv

    if not os.path.exists(HISTORY_FILE):
        return None

    with open(HISTORY_FILE, "r", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))

    # Group by symbol
    from collections import defaultdict
    by_symbol = defaultdict(list)
    for r in rows:
        by_symbol[r["Symbol"]].append(r)

    closed = []

    for sym, trades in by_symbol.items():
        buys = []
        for t in trades:
            if t["Type"] == "BUY":
                buys.append({
                    "shares": float(t["Shares"]),
                    "price": float(t["Price"])
                })
            elif t["Type"] == "SELL":
                sell_shares = float(t["Shares"])
                sell_price = float(t["Price"])

                # Match against buys (FIFO)
                remaining = sell_shares
                cost = 0
                matched = 0

                while remaining > 0 and buys:
                    b = buys[0]
                    take = min(b["shares"], remaining)
                    cost += take * b["price"]
                    matched += take
                    b["shares"] -= take
                    remaining -= take
                    if b["shares"] <= 0:
                        buys.pop(0)

                if matched > 0:
                    avg_buy = cost / matched
                    pct = ((sell_price - avg_buy) / avg_buy) * 100
                    closed.append({
                        "Symbol": sym,
                        "Shares": matched,
                        "BuyAvg": round(avg_buy, 2),
                        "SellPrice": round(sell_price, 2),
                        "Pct": round(pct, 2)
                    })

    if not closed:
        return None

    wins = [c for c in closed if c["Pct"] > 0]
    losses = [c for c in closed if c["Pct"] <= 0]

    return {
        "TotalClosed": len(closed),
        "Wins": len(wins),
        "Losses": len(losses),
        "WinRate": round(len(wins) / len(closed) * 100, 2),
        "AvgGain": round(sum(c["Pct"] for c in wins) / len(wins), 2) if wins else 0,
        "AvgLoss": round(sum(c["Pct"] for c in losses) / len(losses), 2) if losses else 0,
        "Trades": closed
    }
portfolio = pd.read_csv("portfolio.csv")

# Detect changes and log trades
new_events = detect_portfolio_changes(portfolio)

if new_events:
    print("\n=== PORTFOLIO CHANGES DETECTED ===")
    for e in new_events:
        print(f"{e['Type']}  {e['Symbol']}  {e['Shares']} @ {e['Price']}  ({e['Note']})")

# Correct cost-basis total (used for allocation %)
TOTAL_INVESTMENT = float(
    (portfolio["Shares"] * portfolio["BuyPrice"]).sum()
)

# Risk per trade: 1% of portfolio
RISK_PER_TRADE_PCT = 1.0
RISK_PER_TRADE_PKR = TOTAL_INVESTMENT * (RISK_PER_TRADE_PCT / 100)

# Max position size: 10% of portfolio per trade
MAX_POSITION_PCT = 10.0
MAX_POSITION_PKR = TOTAL_INVESTMENT * (MAX_POSITION_PCT / 100)


print(f"Risk per trade: PKR {round(RISK_PER_TRADE_PKR, 2)} ({RISK_PER_TRADE_PCT}%)")
try:
    with open("live_market_data.json", "r") as file:
        live_market_data = json.load(file)

    print("LIVE MARKET DATA LOADED")

except Exception:

    print("LIVE DATA FAILED - USING BACKUP SOURCE")

    try:
        with open("backup_market_data.json", "r") as file:
            backup_data = json.load(file)

        live_market_data = []

    except Exception:

        print("BACKUP SOURCE FAILED")

        live_market_data = []

live_price_map = {
    row["Symbol"]: row["Price"]
    for row in live_market_data
    if isinstance(row, dict)
    and row.get("Price") is not None
}
portfolio_results = []


symbols = [

# OIL & GAS
"OGDC","PPL","MARI","POL","PSO","ATRL","NRL","PRL","CNERGY","APL",

# POWER
"HUBC","KEL","KAPCO","SPWL","NPL",

# FERTILIZER
"FFC","EFERT","FATIMA","ENGRO",

# BANKS
"HBL","UBL","MCB","MEBL","NBP",
"BAFL","BAHL","AKBL","BOP","BIPL",
"FABL","SCBPL",

# CEMENT
"LUCK","DGKC","MLCF","CHCC","FCCL",
"KOHC","PIOC","BWCL","ACPL","FECTC",

# TECHNOLOGY
"SYS","TRG","AVN","NETSOL","OCTOPUS",

# PHARMACEUTICALS
"SEARL","AGP","HINOON","ABOT","GLAXO",
"FEROZ","CPHL",

# CHEMICALS
"EPCL","LOTCHEM","SITC",

# TEXTILE
"NML","GATM","KTML","ILP","NCL",
"ADMM","GADT",

# ENGINEERING & STEEL
"ISL","ASTL","MUGHAL","AGHA",
"INIL","ASL",

# AUTOMOBILE
"INDU","HCAR","GHNI",
"GHGL","MTL",

# FOOD
"NATF","MUREB","UNITY","RMPL",
"SHEZ","NESTLE",

# INSURANCE
"AICL","EFUG","EFUL","JGICL",

# LEATHER & EXPORT
"SRVI","PAKT",

# CABLES & ELECTRICAL
"PAEL","WAVES",

# PORTFOLIO STOCKS
"BNL","GTYR","SPSL"

]
sector_map = {
    "OGDC":"Oil & Gas",
    "PPL":"Oil & Gas",
    "POL":"Oil & Gas",
    "MARI":"Oil & Gas",
    "PSO":"Oil & Gas",
    "ATRL":"Oil & Gas",
    "PRL":"Oil & Gas",

    "HBL":"Banking",
    "UBL":"Banking",
    "MCB":"Banking",
    "NBP":"Banking",
    "BAHL":"Banking",
    "FABL":"Banking",

    "SYS":"Technology",
    "NETSOL":"Technology",
    "TRG":"Technology",
    "AVN":"Technology",
    "OCTOPUS":"Technology",

    "LUCK":"Cement",
    "CHCC":"Cement",
    "KOHC":"Cement",
    "PIOC":"Cement",
    "BWCL":"Cement",

    "FFC":"Fertilizer",
    "EFERT":"Fertilizer",
    "FATIMA":"Fertilizer",

    "HUBC":"Power",
    "KAPCO":"Power"
}

results = []

# ==================================
# NEWS IMPACT ENGINE
# ==================================

news_items = [
    "Oil prices surge sharply because of geopolitical tensions",
    "SBP cuts interest rate",
    "Pakistan rupee depreciates against the US dollar",
]

news_rules = {

    "OIL": {
        "keywords": [
            "oil price",
            "oil prices",
            "crude oil",
            "brent",
            "wti",
            "oil surge",
            "oil rises",
            "oil falls"
        ],
        "stocks": [
            "OGDC", "PPL", "MARI", "POL",
            "PSO", "ATRL", "NRL", "PRL",
            "CNERGY", "APL"
        ]
    },

    "INTEREST RATE": {
        "keywords": [
            "interest rate",
            "policy rate",
            "rate cut",
            "rate hike",
            "interest rates",
            "sbp cuts",
            "sbp raises"
        ],
        "stocks": [
            "HBL", "UBL", "MCB", "MEBL",
            "NBP", "BAFL", "BAHL", "AKBL",
            "BOP", "BIPL", "FABL", "SCBPL"
        ]
    },

    "RUPEE": {
        "keywords": [
            "rupee",
            "pakistani rupee",
            "pkr",
            "currency",
            "devaluation",
            "depreciation",
            "appreciation"
        ],
        "stocks": [
            "SYS", "TRG", "AVN", "NETSOL",
            "NML", "GATM", "KTML", "ILP",
            "NCL", "GADT", "SRVI"
        ]
    },

    "FERTILIZER": {
        "keywords": [
            "fertilizer",
            "urea",
            "gas price",
            "gas supply",
            "fertilizer subsidy"
        ],
        "stocks": [
            "FFC", "EFERT", "FATIMA", "ENGRO"
        ]
    },

    "CEMENT": {
        "keywords": [
            "cement",
            "coal price",
            "construction",
            "infrastructure",
            "cement demand"
        ],
        "stocks": [
            "LUCK", "DGKC", "MLCF", "CHCC",
            "FCCL", "KOHC", "PIOC", "BWCL",
            "ACPL", "FECTC"
        ]
    },

    "POWER": {
        "keywords": [
            "power tariff",
            "electricity tariff",
            "circular debt",
            "power sector",
            "electricity price"
        ],
        "stocks": [
            "HUBC", "KEL", "KAPCO",
            "SPWL", "NPL"
        ]
    },

    "PHARMACEUTICAL": {
        "keywords": [
            "pharmaceutical",
            "medicine price",
            "drug price",
            "drug policy",
            "pharma"
        ],
        "stocks": [
            "SEARL", "AGP", "HINOON",
            "ABOT", "GLAXO", "FEROZ", "CPHL"
        ]
    },

    "GEOPOLITICAL": {
        "keywords": [
            "war",
            "iran",
            "israel",
            "middle east",
            "conflict",
            "geopolitical",
            "hormuz",
            "sanctions"
        ],
        "stocks": [
            "OGDC", "PPL", "MARI", "POL",
            "PSO", "ATRL", "NRL", "PRL",
            "HUBC", "LUCK"
        ]
    }
}


def analyze_news(headline):

    text = headline.lower()

    detected_categories = []

    for category, rule in news_rules.items():

        for keyword in rule["keywords"]:

            if keyword in text:
                detected_categories.append(category)
                break

    detected_categories = list(
        dict.fromkeys(detected_categories)
    )

    if not detected_categories:
        return {
            "Headline": headline,
            "Category": "OTHER",
            "Direction": "UNKNOWN",
            "Impact": "LOW",
            "AffectedStocks": []
        }

    # ----------------------------------
    # Direction
    # ----------------------------------

    positive_words = [
        "surge",
        "rise",
        "rises",
        "increase",
        "increases",
        "cut",
        "cuts",
        "growth",
        "strong",
        "improve",
        "improves",
        "approval",
        "positive"
    ]

    negative_words = [
        "fall",
        "falls",
        "drop",
        "drops",
        "decline",
        "declines",
        "hike",
        "hikes",
	"depreciates",
        "depreciation",
        "crisis",
        "loss",
        "negative",
        "ban",
        "shortage",
        "sanction"
    ]

    positive = sum(
        1 for word in positive_words
        if word in text
    )

    negative = sum(
        1 for word in negative_words
        if word in text
    )

    if positive > negative:
        direction = "POSITIVE"

    elif negative > positive:
        direction = "NEGATIVE"

    else:
        direction = "MIXED"

    # ----------------------------------
    # Impact
    # ----------------------------------

    if len(detected_categories) >= 2:
        impact = "HIGH"

    elif any(
        category in [
            "OIL",
            "INTEREST RATE",
            "RUPEE",
            "GEOPOLITICAL"
        ]
        for category in detected_categories
    ):
        impact = "HIGH"

    else:
        impact = "MEDIUM"

    # ----------------------------------
    # Affected Stocks
    # ----------------------------------

    affected_stocks = []

    for category in detected_categories:

        affected_stocks.extend(
            news_rules[category]["stocks"]
        )

    affected_stocks = list(
        dict.fromkeys(affected_stocks)
    )

    return {
        "Headline": headline,
        "Category": ", ".join(
            detected_categories
        ),
        "Direction": direction,
        "Impact": impact,
        "AffectedStocks": affected_stocks
    }


# ==================================
# PROCESS NEWS
# ==================================

news_results = []

for headline in news_items:

    news_results.append(
        analyze_news(headline)
    )
# ==================================
# DISPLAY NEWS IMPACT
# ==================================

print("\n=== NEWS IMPACT ===")

for news in news_results:

    print("Event:", news["Headline"])
    print("Category:", news["Category"])
    print("Direction:", news["Direction"])
    print("Impact:", news["Impact"])
    print("Affected Stocks:", ", ".join(news["AffectedStocks"]))
    print("-" * 50)
for symbol in symbols:

    data = None

    # Try yfinance first
    try:
        data = yf.Ticker(symbol + ".KA").history(period="1y")
        if data is None or len(data) == 0:
            data = None
    except Exception:
        data = None

    # Fallback to psxdata
    if data is None:
        try:
            import psxdata
            psx_df = psxdata.stocks(symbol)

            if psx_df is not None and len(psx_df) > 0:
                # Normalize to yfinance-style
                psx_df = psx_df.rename(columns={
                    "date": "Date",
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                })
                psx_df["Date"] = pd.to_datetime(psx_df["Date"])
                psx_df = psx_df.sort_values("Date").set_index("Date")
                data = psx_df[["Open", "High", "Low", "Close", "Volume"]].tail(252)
                print(f"{symbol} | Using psxdata fallback ({len(data)} rows)")
        except Exception as e:
            print(f"{symbol} | psxdata failed: {e}")
            data = None

    if data is None or len(data) < 50:
        continue

    data["MA20"] = data["Close"].rolling(20).mean()
    data["MA50"] = data["Close"].rolling(50).mean()

    delta = data["Close"].diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    data["RSI"] = 100 - (100 / (1 + rs))
    data["TR"] = (
    data["High"] - data["Low"]
    )

    data["ATR"] = data["TR"].rolling(14).mean()

    latest = data.iloc[-1]
    rsi = latest["RSI"]
    atr = latest["ATR"]
    previous = data.iloc[-2]
    bullish_engulfing = (

        previous["Close"] < previous["Open"]

        and

        latest["Close"] > latest["Open"]

        and

        latest["Close"] > previous["Open"]

        and

        latest["Open"] < previous["Close"]

    )
    bearish_engulfing = (

        previous["Close"] > previous["Open"]

        and

        latest["Close"] < latest["Open"]

        and

        latest["Open"] > previous["Close"]

        and

        latest["Close"] < previous["Open"]

    )

    avg_volume = data["Volume"].rolling(20).mean().iloc[-1]
    current_volume = latest["Volume"]

    # =====================
    # VOLUME ANALYSIS
    # =====================

    if current_volume > avg_volume * 2:
        volume_status = "VOLUME SPIKE"

    elif current_volume > avg_volume * 1.2:
        volume_status = "HIGH VOLUME"

    elif current_volume < avg_volume * 0.8:
        volume_status = "LOW VOLUME"

    else:
        volume_status = "NORMAL VOLUME"

    # =====================
    # BREAKOUT ANALYSIS
    # =====================
    highest_20 = data["High"].tail(20).max()
    breakout = latest["Close"] > highest_20
   

    distance = (
        (latest["Close"] / highest_20) - 1
    ) * 100

    if distance > 5 and current_volume > avg_volume * 2:
        breakout_status = "EXPLOSIVE BREAKOUT"
        breakout_strength = 100
        breakout = True

    elif distance > 2 and current_volume > avg_volume * 1.5:
        breakout_status = "STRONG BREAKOUT"
        breakout_strength = 80
        breakout = True

    elif distance > 0:
        breakout_status = "MEDIUM BREAKOUT"
        breakout_strength = 60
        breakout = True

    elif latest["Close"] > highest_20 * 0.98:
        breakout_status = "NEAR BREAKOUT"
        breakout_strength = 40
        breakout = False

    else:
        breakout_status = "NO BREAKOUT"
        breakout_strength = 0
        breakout = False
    
    # =====================
    # BULLISH DIVERGENCE
    # =====================

    bullish_divergence = "NO"

    try:

        recent_price = data["Close"].tail(14)
        recent_rsi = data["RSI"].tail(14)

        price_old = recent_price.iloc[:7].min()
        price_new = recent_price.iloc[7:].min()

        rsi_old = recent_rsi.iloc[:7].min()
        rsi_new = recent_rsi.iloc[7:].min()

        if price_new < price_old and rsi_new > rsi_old:
            bullish_divergence = "YES"

    except:
        bullish_divergence = "NO"

    # =====================
    # BEARISH DIVERGENCE
    # =====================

    bearish_divergence = "NO"

    try:

        recent_price = data["Close"].tail(14)
        recent_rsi = data["RSI"].tail(14)

        price_old = recent_price.iloc[:7].max()
        price_new = recent_price.iloc[7:].max()

        rsi_old = recent_rsi.iloc[:7].max()
        rsi_new = recent_rsi.iloc[7:].max()

        if price_new > price_old and rsi_new < rsi_old:
            bearish_divergence = "YES"

    except:
        bearish_divergence = "NO"

    range_20 = (
        data["High"].tail(20).max()
        - data["Low"].tail(20).min()
)
    
     
    accumulation = (
        current_volume > avg_volume * 1.2
        and rsi > 45
        and rsi < 65
        and range_20 / latest["Close"] < 0.15
    )

    distribution = (
        current_volume > avg_volume * 1.2
        and rsi > 65
        and latest["Close"] < latest["MA20"]
    )


    price_20_days_ago = data["Close"].iloc[-20]

    relative_strength = (
    (latest["Close"] - price_20_days_ago)
    / price_20_days_ago
    ) * 100

    try:

        if len(data) >= 90:

            price_60_days_ago = data["Close"].iloc[-60]
            price_90_days_ago = data["Close"].iloc[-90]

            trend_3m = (
                (latest["Close"] - price_60_days_ago)
                / price_60_days_ago
            ) * 100

            trend_6m = (
                (latest["Close"] - price_90_days_ago)
                / price_90_days_ago
            ) * 100

        else:

            trend_3m = 0
            trend_6m = 0

    except:

        trend_3m = 0
        trend_6m = 0
    
    
    if trend_3m > 20 and trend_6m > 30:
        market_trend = "SUPER BULLISH"

    elif trend_3m > 10:
        market_trend = "BULLISH"

    elif trend_3m > -10:
        market_trend = "NEUTRAL"

    else:
        market_trend = "BEARISH"


    # ==========================
    # MULTI TIMEFRAME SCORE
    # ==========================

    mtf_score = 0

    if trend_3m > 10:
        mtf_score += 50

    if trend_6m > 20:
        mtf_score += 50

    # =========================
    # TREND STATUS
    # =========================
    
    trend_score = 0

    if latest["Close"] > latest["MA20"]:
        trend_score += 1

    if latest["MA20"] > latest["MA50"]:
        trend_score += 1

    if relative_strength > 0:
        trend_score += 1

    if trend_score == 3:
        trend_status = "STRONG UPTREND"

    elif trend_score == 2:
        trend_status = "UPTREND"

    elif trend_score == 1:
        trend_status = "SIDEWAYS"

    else:
        trend_status = "DOWNTREND"





    highest_20 = data["High"].tail(20).max()

    breakout = latest["Close"] > highest_20

    recent_low = data["Low"].tail(10).min()

    support = round(data["Low"].tail(20).min(), 2)

    resistance = round(data["High"].tail(20).max(), 2)

    accumulation = (
        current_volume > avg_volume * 1.2
        and rsi > 45
        and rsi < 65
        and latest["Close"] > latest["MA20"]
    )

    liquidity_sweep_buy = (
    latest["Low"] < recent_low and
    latest["Close"] > recent_low
    )
    
    distribution = (
        current_volume > avg_volume
        and latest["Close"] < latest["MA20"]
    )

    score = 0

    if latest["Close"] > latest["MA20"]:
        score += 1

    if latest["MA20"] > latest["MA50"]:
        score += 1
    if current_volume > avg_volume:
        score += 1

    if breakout:
        score += 1
    if accumulation:
        score += 1
    if distribution:
        score -= 1
    if bullish_divergence == "YES":
        score += 1

    if bearish_divergence == "YES":
        score -= 1

    
    if breakout:
        breakout_strength = 50
    else:
        breakout_strength = 0

    if current_volume > avg_volume:
        breakout_strength += 25

    if relative_strength > 0:
        breakout_strength += 25

    breakout_strength = min(breakout_strength, 100)

    if liquidity_sweep_buy:
        score += 1
    if accumulation:
        score += 1
    if distribution:
        score -= 1
    if bullish_engulfing:
        score += 1
    if bearish_engulfing:
        score -= 1
    if volume_status == "VOLUME SPIKE":
        score += 2

    elif volume_status == "HIGH VOLUME":
        score += 1
    if accumulation:
        score += 1

    if score >= 4 and rsi < 65:
        signal = "STRONG BUY"

    elif score >= 2 and rsi < 70:
        signal = "BUY"

    elif rsi < 30:
        signal = "WATCH"

    elif score == 1:
        signal = "HOLD"

    elif score <= -1:
        signal = "STRONG SELL"

    else:
        signal = "SELL"

    entry_timing = ""

    pullback_score = 0

    if signal in ["BUY", "STRONG BUY"]:

        # Price close to MA20 = possible pullback zone
        if latest["Close"] <= latest["MA20"] * 1.03:
            pullback_score += 30

        # Healthy RSI for a pullback entry
        if rsi >= 40 and rsi <= 60:
            pullback_score += 20

        # Price near support
        if support > 0 and latest["Close"] <= support * 1.05:
            pullback_score += 20

        # Bullish divergence supports a pullback
        if bullish_divergence == "YES":
            pullback_score += 15

        # Liquidity sweep can confirm a pullback reversal
        if liquidity_sweep_buy:
            pullback_score += 15

        pullback_score = min(pullback_score, 100)

        if rsi > 70:
            entry_timing = "OVEREXTENDED"

        elif pullback_score >= 70:
            entry_timing = "STRONG PULLBACK ENTRY"

        elif pullback_score >= 50:
            entry_timing = "PULLBACK ENTRY"

        elif breakout:
            entry_timing = "BREAKOUT ENTRY"

        elif latest["Close"] < latest["MA20"] * 1.05:
            entry_timing = "WAIT FOR PULLBACK"

        else:
            entry_timing = "WAIT"

    else:
        entry_timing = "AVOID ENTRY"



    buy_price = round(latest["Close"], 2)
    
    live_price = live_price_map.get(symbol)

    stop_loss = round(
        buy_price - (atr * 2),
        2
    )

    target1 = round(
        buy_price + (atr * 3),
        2
    )

    target2 = round(
        buy_price + (atr * 5),
        2
    )
    # ---- Entry Price Range (Buy Zone) ----
    if signal in ["BUY", "STRONG BUY"]:
        buy_zone_low = round(
            max(support, buy_price - (atr * 1.0)),
            2
        )
        buy_zone_high = round(
            buy_price + (atr * 0.5),
            2
        )
        buy_zone_note = f"BUY {buy_zone_low} – {buy_zone_high}"
    else:
        buy_zone_low = None
        buy_zone_high = None
        buy_zone_note = ""

    risk = buy_price - stop_loss

    reward = target1 - buy_price

    rr_ratio = round(reward / risk, 2)
    confidence = min(score * 20, 100)
    

    pattern = ""

    if bullish_engulfing:
        pattern = "Bullish Engulfing"

    if bearish_engulfing:
        pattern += "Bearish Engulfing "

    if accumulation:
        pattern += "Accumulation "
    
    if distribution:
        pattern += "Distribution "

    # ==================================
    # OPPORTUNITY SCORE
    # ==================================

    opportunity_score = 0

    opportunity_score += score * 10

    if volume_status == "VOLUME SPIKE":
        opportunity_score += 15

    elif volume_status == "HIGH VOLUME":
        opportunity_score += 10

    opportunity_score += breakout_strength // 2

    if bullish_divergence == "YES":
        opportunity_score += 15

    if bearish_divergence == "YES":
        opportunity_score -= 15

    if accumulation:
        opportunity_score += 10

    if distribution:
        opportunity_score -= 20

    if signal == "SELL":
        opportunity_score -= 60

    if signal == "STRONG SELL":
        opportunity_score -= 80

    if rsi > 70:
        opportunity_score -= 30
    if rsi > 80:
        opportunity_score -= 50

    opportunity_score = max(0, min(opportunity_score, 100))




    # ==================================
    # MOMENTUM SCORE
    # ==================================

    momentum_score = 0

    if latest["Close"] > latest["MA20"]:
        momentum_score += 30

    if latest["MA20"] > latest["MA50"]:
        momentum_score += 30

    if current_volume > avg_volume:
        momentum_score += 20

    if relative_strength > 0:
        momentum_score += 20

    momentum_score = min(momentum_score, 100)

    smart_money_confidence = 0

    if accumulation:
        smart_money_confidence += 40

    if volume_status == "VOLUME SPIKE":
        smart_money_confidence += 20

    if breakout:
        smart_money_confidence += 20
    
    if bullish_divergence == "YES":
        smart_money_confidence += 20

    if liquidity_sweep_buy:
        smart_money_confidence += 10

    if bullish_engulfing:
        smart_money_confidence += 10

    if distribution:
        smart_money_confidence -= 20

    if bearish_divergence == "YES":
        smart_money_confidence -= 20

    if bearish_engulfing:
        smart_money_confidence -= 10

    smart_money_confidence = max(
        0,
        min(smart_money_confidence, 100)
    )


    # ==================================
    # LONG TERM SCORE
    # ==================================

    long_term_score = 0

    if latest["Close"] > latest["MA50"]:
        long_term_score += 30

    if relative_strength > 0:
        long_term_score += 25

    if rsi > 45:
        long_term_score += 20

    if confidence > 50:
        long_term_score += 25

    long_term_score = min(long_term_score, 100)

    # ==================================
    # TRADE STYLE CLASSIFICATION
    # ==================================

    if signal in ("BUY", "STRONG BUY"):

        # SHORT first — breakout + momentum is time-sensitive
        if (momentum_score >= 80
            and breakout_status in (
                "NEAR BREAKOUT", "MEDIUM BREAKOUT",
                "STRONG BREAKOUT", "EXPLOSIVE BREAKOUT"
            )):
            trade_style = "SHORT"
            style_reason = "Momentum + breakout zone"

        # SWING — pullback entry
        elif pullback_score >= 50:
            trade_style = "SWING"
            style_reason = "Pullback entry"

        # LONG — strong trend, healthy RSI (not overbought)
        elif (long_term_score >= 80
              and trend_status in ("STRONG UPTREND", "UPTREND")
              and rsi >= 45 and rsi <= 65):
            trade_style = "LONG"
            style_reason = "Strong trend, healthy RSI"

        else:
            trade_style = "SWING"
            style_reason = "Buy signal (default swing)"

    else:
        trade_style = "-"
        style_reason = ""

    results.append({
        "Symbol": symbol,
        "Sector": sector_map.get(symbol, "Other"),
        "Close": buy_price,
	"LivePrice": live_price_map.get(symbol),
        "RSI": round(rsi, 2),
        "RS": round(relative_strength, 2),
        "Confidence": confidence,
        "Score": score,
        "Signal": signal,
	"MTFScore": mtf_score,

        "VolumeStatus": volume_status,
        "BreakoutStatus": breakout_status,
        "BullishDivergence": bullish_divergence,
	"BearishDivergence": bearish_divergence,

	"OpportunityScore": opportunity_score,
        "MomentumScore": momentum_score,
        "LongTermScore": long_term_score,
	
	"TrendStatus": trend_status,
        "BreakoutStrength": breakout_strength,
	"SmartMoneyConfidence": smart_money_confidence,


	"SmartMoneyConfidence": smart_money_confidence,
	"MarketTrend": market_trend,
  
        "EntryTiming": entry_timing,
	"PullbackScore": pullback_score,
        "Pattern": pattern,
        "Support": support,
        "Resistance": resistance,
        "RR": rr_ratio,

	
	
        "StopLoss": stop_loss,
        "Target1": target1,
        "Target2": target2,
	"LiquiditySweep": "YES" if liquidity_sweep_buy else "NO",
        "BuyZoneLow": buy_zone_low,
        "BuyZoneHigh": buy_zone_high,
        "BuyZoneNote": buy_zone_note,
        "PositionSize": 0,
        "PositionRiskPKR": 0,
        "PositionAction": "",
        "TradeStyle": trade_style,
        "StyleReason": style_reason
    })

df = pd.DataFrame(results)

sector_rank = (
    df.groupby("Sector")["Confidence"]
    .mean()
    .sort_values(ascending=False)
)

print("\n=== SECTOR RANKING ===")
print(sector_rank)

df["MasterScore"] = (
    df["OpportunityScore"] * 0.35
    + df["MomentumScore"] * 0.25
    + df["LongTermScore"] * 0.20
    + df["SmartMoneyConfidence"] * 0.10
    + df["MTFScore"] * 0.10
)
df = df.sort_values(
    "MasterScore",
    ascending=False
)

# ==================================
# AI DECISION ENGINE
# ==================================

def ai_decision(row):

    score = row["MasterScore"]

    signal = row["Signal"]
    rsi = row["RSI"]
    pullback = row["PullbackScore"]
    smart_money = row["SmartMoneyConfidence"]
    entry_timing = row["EntryTiming"]

    # ----------------------------------
    # STRONG BUY
    # ----------------------------------

    if (
        score >= 80
        and signal in ["BUY", "STRONG BUY"]
        and smart_money >= 60
        and pullback >= 70
        and rsi < 70
    ):
        return "STRONG BUY"

    # ----------------------------------
    # BUY NOW
    # ----------------------------------

    elif (
        score >= 65
        and signal in ["BUY", "STRONG BUY"]
        and rsi < 70
        and pullback >= 50
        and entry_timing in [
            "PULLBACK ENTRY",
            "STRONG PULLBACK ENTRY",
            "BREAKOUT ENTRY"
        ]
    ):
        return "BUY"

    # ----------------------------------
    # BUY - WAIT FOR PULLBACK
    # ----------------------------------

    elif (
        score >= 65
        and signal in ["BUY", "STRONG BUY"]
        and pullback < 50
    ):
        return "BUY - WAIT FOR PULLBACK"

    # ----------------------------------
    # HOLD / WATCH
    # ----------------------------------

    elif (
        score >= 45
        and signal in ["BUY", "STRONG BUY", "WATCH"]
    ):
        return "HOLD-WATCH"

    # ----------------------------------
    # SELL
    # ----------------------------------

    elif (
        score < 45
        or signal == "SELL"
    ):
        return "SELL"

    # ----------------------------------
    # STRONG SELL
    # ----------------------------------

    else:
        return "STRONG SELL"
df["AIDecision"] = df.apply(
    ai_decision,
    axis=1
)
# Log today's signals to history
logged = log_signal_history(df)

if logged > 0:
    print(f"\n📝 Signal history: {logged} signals logged for today")

# Build current portfolio map for sizing
current_portfolio_map = {}
for _, r in portfolio.iterrows():
    current_portfolio_map[r["Symbol"]] = {
        "Shares": int(r["Shares"]),
        "BuyPrice": float(r["BuyPrice"])
    }

# Apply position sizing to every row
sizes = df.apply(
    lambda row: calculate_position_size(row, current_portfolio_map),
    axis=1
)

df["PositionSize"] = [s[0] for s in sizes]
df["PositionRiskPKR"] = [s[1] for s in sizes]
df["PositionAction"] = [s[2] for s in sizes]

print("\n=== PSX STOCK RANKING ===")
print(df)

elite_entries = df[
    (df["OpportunityScore"] >= 60)
    &
    (df["Signal"].isin(
        ["BUY", "STRONG BUY"]
    ))
]
elite_entries = elite_entries.sort_values(
    "MasterScore",
    ascending=False
)

print("\n=== ELITE ENTRY LIST ===")

print(
    elite_entries[
        [
            "Symbol",
            "Signal",
            "MasterScore",
            "OpportunityScore",
            "MomentumScore",
            "LongTermScore",
	    "EntryTiming",
            "PullbackScore"
        ]
    ].head(10)
)

top = df.sort_values(
    by="OpportunityScore",
    ascending=False
)

print(
    top[
        [
            "Symbol",
            "Signal",
            "OpportunityScore",
            "MomentumScore",
            "LongTermScore",
            "VolumeStatus",
            "BreakoutStatus"
        ]
    ].head(10)
)


# ==================================
# ADD NEWS IMPACT TO REPORT
# ==================================

news_df = pd.DataFrame(news_results)

if not news_df.empty:
    news_df.to_excel(
        "psx_news_impact.xlsx",
        index=False
    )

df.to_excel("psx_report.xlsx", index=False)



df.to_json(
    "psx_report.json",
    orient="records",
    indent=4
)

print("\nReport saved as psx_report.xlsx")
print("Report saved as psx_report.json")
print("\n=== AI RECOMMENDATION ===")

buy_list = df[df["Signal"] == "BUY"]["Symbol"].tolist()
watch_list = df[df["Signal"] == "WATCH"]["Symbol"].tolist()

print("BUY:", ", ".join(buy_list))
print("WATCH:", ", ".join(watch_list))
sender_email = GMAIL_SENDER
app_password = GMAIL_APP_PASSWORD
stats = calculate_trade_stats()
# ==================================
# ACTION FEED (1.5 + 1.6)
# ==================================

def evaluate_reasons(r):
    """Return list of matched reasons + confidence."""
    reasons = []

    if r.get("PullbackScore", 0) >= 50:
        reasons.append("Pullback zone")

    if r.get("BullishDivergence") == "YES":
        reasons.append("Bullish divergence")

    if "Accumulation" in str(r.get("Pattern", "")):
        reasons.append("Accumulation")

    if r.get("VolumeStatus") in ("VOLUME SPIKE", "HIGH VOLUME"):
        reasons.append(f"Volume: {r['VolumeStatus']}")

    if r.get("SmartMoneyConfidence", 0) >= 40:
        reasons.append(f"Smart money {r['SmartMoneyConfidence']}")

    if r.get("BreakoutStatus") in ("MEDIUM BREAKOUT", "STRONG BREAKOUT", "EXPLOSIVE BREAKOUT"):
        reasons.append(r["BreakoutStatus"])

    confidence = min(len(reasons) * 20, 100)
    return reasons, confidence


buy_now = []
wait_list = []
exit_list = []
watch_list = []

held_symbols = {
    r["Symbol"]: {"BuyPrice": float(r["BuyPrice"]), "Shares": int(r["Shares"])}
    for _, r in portfolio.iterrows()
}

for _, r in df.iterrows():
    sig = r["Signal"]
    rsi = r["RSI"]
    sym = r["Symbol"]

    reasons, conf = evaluate_reasons(r)

    # EXIT check first (holds override buys)
    if sym in held_symbols:
        pl = ((r["LivePrice"] or r["Close"]) - held_symbols[sym]["BuyPrice"]) / held_symbols[sym]["BuyPrice"] * 100
        if r["PositionAction"].startswith("EXIT") or pl <= -15:
            exit_list.append({
                "Symbol": sym,
                "Price": r["LivePrice"] or r["Close"],
                "LossPct": round(pl, 2),
                "Reason": r["PositionAction"] if r["PositionAction"].startswith("EXIT") else "Heavy loss"
            })
            continue

    # BUY NOW
    if sig in ("BUY", "STRONG BUY") and rsi < 70 and len(reasons) >= 3:
        buy_now.append({
            "Symbol": sym,
            "Price": round(r["Close"], 2),
            "Shares": int(r["PositionSize"]),
            "Target1": r["Target1"],
            "StopLoss": r["StopLoss"],
            "Confidence": conf,
            "Reasons": reasons
        })
        continue

    # WAIT
    if sig in ("BUY", "STRONG BUY") and r["BuyZoneNote"]:
        wait_list.append({
            "Symbol": sym,
            "BuyZone": r["BuyZoneNote"],
            "Confidence": conf,
            "Reasons": reasons if reasons else ["No strong confirmation yet"]
        })
        continue

    # WATCH
    if sig in ("WATCH", "HOLD"):
        watch_list.append({
            "Symbol": sym,
            "Signal": sig,
            "RSI": rsi,
            "Confidence": conf
        })

# Sort by confidence
buy_now.sort(key=lambda x: -x["Confidence"])
wait_list.sort(key=lambda x: -x["Confidence"])

# Save to JSON
actions_payload = {
    "generated": datetime.now().isoformat(),
    "buy_now": buy_now,
    "wait": wait_list,
    "exit": exit_list,
    "watch": watch_list
}

with open("psx_actions.json", "w") as f:
    json.dump(actions_payload, f, indent=4)

print("\n=== TODAY'S ACTIONS ===")

print(f"\n🟢 BUY NOW ({len(buy_now)})")
for a in buy_now[:10]:
    print(f"  {a['Symbol']:6} @ {a['Price']:>9} | {a['Shares']:>5} sh | "
          f"T1: {a['Target1']:>9} | Stop: {a['StopLoss']:>9} | "
          f"Conf: {a['Confidence']}%")
    print(f"         ↳ {', '.join(a['Reasons'])}")

print(f"\n🟡 WAIT FOR PULLBACK ({len(wait_list)})")
for a in wait_list[:10]:
    print(f"  {a['Symbol']:6} | {a['BuyZone']:30} | Conf: {a['Confidence']}%")

print(f"\n🔴 EXIT ({len(exit_list)})")
for a in exit_list:
    print(f"  {a['Symbol']:6} @ {a['Price']:>9} | P/L: {a['LossPct']}% | {a['Reason']}")

print(f"\n👀 WATCH ({len(watch_list)})")
for a in watch_list[:10]:
    print(f"  {a['Symbol']:6} | Signal: {a['Signal']:8} | RSI: {a['RSI']}")
sizing_view = df[
    df["PositionAction"].str.contains("BUY|ADD|EXIT", na=False)
].sort_values("MasterScore", ascending=False)
msg = EmailMessage()
msg["Subject"] = "PSX Daily Alert"
msg["From"] = sender_email
msg["To"] = sender_email

email_text = "=== PSX DAILY REPORT ===\n\n"

for _, row in df.iterrows():

    email_text += (
        f"{row['Symbol']}\n"
        f"Price: {row['Close']}\n"
        f"RSI: {row['RSI']}\n"
        f"Score: {row['Score']}\n"
        f"Signal: {row['Signal']}\n"
        f"Target1: {row['Target1']}\n"
        f"Target2: {row['Target2']}\n"
        f"StopLoss: {row['StopLoss']}\n"
        "-------------------------\n"
    )
email_text += "\n=== POSITION SIZING ===\n"
for _, r in sizing_view.head(10).iterrows():
    email_text += f"{r['Symbol']} | {r['PositionAction']} | Risk: PKR {r['PositionRiskPKR']}\n"
email_text += "\n=== TODAY'S ACTIONS ===\n"

email_text += f"\nBUY NOW ({len(buy_now)}):\n"
for a in buy_now[:8]:
    email_text += f"  {a['Symbol']} @ {a['Price']} | {a['Shares']} sh | T1: {a['Target1']} | Stop: {a['StopLoss']} | Conf: {a['Confidence']}%\n"

email_text += f"\nWAIT ({len(wait_list)}):\n"
for a in wait_list[:8]:
    email_text += f"  {a['Symbol']} | {a['BuyZone']}\n"

email_text += f"\nEXIT ({len(exit_list)}):\n"
for a in exit_list:
    email_text += f"  {a['Symbol']} @ {a['Price']} | {a['LossPct']}% | {a['Reason']}\n"


email_text += "\n=== TRADE STATISTICS ===\n"
if stats:
    email_text += (
        f"Closed Trades: {stats['TotalClosed']}\n"
        f"Win Rate: {stats['WinRate']}%\n"
        f"Avg Gain: +{stats['AvgGain']}%\n"
        f"Avg Loss: {stats['AvgLoss']}%\n"
    )
else:
    email_text += "No closed trades yet.\n"

msg.set_content(email_text)
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(sender_email, app_password)
    smtp.send_message(msg)

print("\nEmail alert sent!")

buy_count = len(df[df["Signal"].isin(["BUY", "STRONG BUY"])])
watch_count = len(df[df["Signal"] == "WATCH"])
sell_count = len(df[df["Signal"] == "SELL"])

if buy_count > sell_count:
    market_trend = "BULLISH"
    risk_level = "LOW"

elif sell_count > buy_count:
    market_trend = "BEARISH"
    risk_level = "HIGH"

else:
    market_trend = "SIDEWAYS"
    risk_level = "MEDIUM"

print("\n=== MARKET STATUS ===")
print("Market Trend:", market_trend)
print("Buy Signals:", buy_count)
print("Watch Signals:", watch_count)
print("Sell Signals:", sell_count)
print("Risk Level:", risk_level)
print("\n=== SMART MONEY PICKS ===")

smart_money = df[
    df["Signal"].isin(
        ["BUY", "STRONG BUY"]
    )
]

smart_money = smart_money.sort_values(
    "SmartMoneyConfidence",
    ascending=False
).head(10)
print(
    smart_money[
        ["Symbol", "Sector", "Signal", "Confidence"]
    ].head(5)
)

print("\n=== SMART MONEY FLOW ===")

accumulation_df = df[
    df["Pattern"].str.contains(
        "Accumulation",
        na=False
    )
]

distribution_df = df[
    df["Pattern"].str.contains(
        "Distribution",
        na=False
    )
]

print("\nACCUMULATION")

print(
    accumulation_df[
        ["Symbol", "Sector", "RSI", "Confidence"]
    ].head(10)
)

print("\nDISTRIBUTION")

print(
    distribution_df[
        ["Symbol", "Sector", "RSI", "Confidence"]
    ].head(10)
)


print("\n=== MY PORTFOLIO ===")
total_investment = 0
total_current_value = 0

best_stock = ""
best_return = -999

worst_stock = ""
worst_return = 999

winning_positions = 0
losing_positions = 0

for index, row in portfolio.iterrows():

    symbol = row["Symbol"]
    buy_price = row["BuyPrice"]

    target1 = row["TargetPrice"]
    target2 = target1

    shares = row["Shares"]

    current_price = live_price_map.get(symbol)

    # Try to get history only if we don't have a live price
    if current_price is None:
        try:
            data = yf.Ticker(symbol + ".KA").history(period="5d")

            if len(data) > 0:
                current_price = round(data["Close"].iloc[-1], 2)
            else:
                current_price = float(buy_price)
                print(f"{symbol} | No market data — using buy price ({current_price})")

        except Exception:
            current_price = float(buy_price)
            print(f"{symbol} | Fetch failed — using buy price ({current_price})")

    
    if current_price >= target2:
        print(f"🎯 TARGET 2 HIT - FULL PROFIT TARGET: {symbol}")

    elif current_price >= target1:
        print(f"🎯 TARGET 1 HIT - CONSIDER SELLING 50%: {symbol}")

    elif current_price >= target1 * 0.95:
        print(f"⚠ APPROACHING TARGET 1: {symbol}")
    profit_pct = round(
        ((current_price - buy_price) / buy_price) * 100,
        2
    )
    stop_action = "KEEP STOP"
    stop_loss_alert = "NO STOP LOSS ALERT"
    sell_alert = "NO SELL ALERT"

    if profit_pct <= -10:
        sell_alert = "SELL ALERT - LOSS LIMIT"

    elif profit_pct >= 15:
        sell_alert = "SELL ALERT - PROFIT PROTECTION"

    elif profit_pct >= 10:
        sell_alert = "SELL ALERT - TAKE PROFIT"

    if profit_pct >= 15:
        new_stop = round(current_price * 0.95, 2)
        stop_action = f"TRAIL STOP TO {new_stop}"

    elif profit_pct >= 10:
        new_stop = round(current_price * 0.93, 2)
        stop_action = f"RAISE STOP TO {new_stop}"

    elif profit_pct >= 5:
        new_stop = round(buy_price, 2)
        stop_action = f"MOVE STOP TO BREAKEVEN {new_stop}"

    if current_price <= buy_price * 0.90:
        stop_loss_alert = "STOP LOSS ALERT - EXIT"

    elif current_price <= buy_price * 0.95:
        stop_loss_alert = "STOP LOSS ALERT - WARNING"



    investment = buy_price * shares
    current_value = current_price * shares

    # NOTE: don't add to total_investment here anymore
    total_current_value += current_value

    if profit_pct > best_return:
        best_return = profit_pct
        best_stock = symbol

    if profit_pct < worst_return:
        worst_return = profit_pct
        worst_stock = symbol

    if profit_pct >= 0:
        winning_positions += 1
    else:
        losing_positions += 1

    stock_row = df[df["Symbol"] == symbol]

    if not stock_row.empty:

        signal = stock_row.iloc[0]["Signal"]
        master_score = stock_row.iloc[0]["MasterScore"]

    else:

        signal = "SELL"
        master_score = 0

    if signal == "STRONG BUY":
        action = "ADD / HOLD"

    elif signal == "BUY":
        action = "HOLD"

    elif signal == "WATCH":
        action = "WATCH CLOSELY"

    elif signal == "SELL":
        action = "REDUCE POSITION"

    elif signal == "STRONG SELL":
        action = "EXIT"

    else:
        action = "HOLD"

    exit_alert = "NO EXIT ALERT"

    if signal == "STRONG SELL":
        exit_alert = "EXIT ALERT - AI SELL SIGNAL"

    elif profit_pct <= -15:
        exit_alert = "EXIT ALERT - HEAVY LOSS"

    elif profit_pct >= 20:
        exit_alert = "EXIT ALERT - LOCK PROFITS"
    

    print(
        f"{symbol} | Buy: {buy_price} | Current: {current_price} | "
        f"P/L: {profit_pct}% | {action} | {stop_action} | "
        f"{sell_alert} | {stop_loss_alert} | {exit_alert}"
    )

    # ---- Auto Portfolio Rebalancer ----
    if profit_pct <= -20:
        rebalance_action = "EXIT"
    elif profit_pct <= -10:
        rebalance_action = "REDUCE"
    elif profit_pct < 10:
        rebalance_action = "HOLD"
    else:
        rebalance_action = "ADD"

    portfolio_results.append({
        "Symbol": symbol,
        "PLPercent": profit_pct,
        "Action": rebalance_action
    })
    # -----------------------------------
print("\n=== PORTFOLIO SUMMARY ===")

total_investment = TOTAL_INVESTMENT   # use correct fixed total

portfolio_pl = round(
    ((total_current_value - TOTAL_INVESTMENT)
    / TOTAL_INVESTMENT) * 100,
    2
)

print("Total Investment:", round(TOTAL_INVESTMENT, 2))


print("Current Value:", round(total_current_value, 2))
print("Portfolio Return:", portfolio_pl, "%")

print("Winning Positions:", winning_positions)
print("Losing Positions:", losing_positions)

print(
    "Best Performer:",
    best_stock,
    "(",
    round(best_return, 2),
    "%)"
)

print(
    "Worst Performer:",
    worst_stock,
    "(",
    round(worst_return, 2),
    "%)"
)
# Log portfolio value for today
log_portfolio_value(
    TOTAL_INVESTMENT,
    total_current_value,
    portfolio_pl
)

print(f"📊 Portfolio value logged for today")


print(f"\n=== POSITION SIZING (Risk {RISK_PER_TRADE_PCT}% = PKR {round(RISK_PER_TRADE_PKR, 2)} per trade) ===")


if not sizing_view.empty:
    for _, r in sizing_view.head(15).iterrows():
        print(
            f"{r['Symbol']:6} | Entry: {r['Close']:>8} | "
            f"Stop: {r['StopLoss']:>8} | "
            f"Risk/share: {round(r['Close'] - r['StopLoss'], 2):>7} | "
            f"{r['PositionAction']}"
        )
else:
    print("No actionable positions right now.")

print("\n=== TRADE STATISTICS ===")



if stats:
    print(f"Total Closed Trades: {stats['TotalClosed']}")
    print(f"Wins: {stats['Wins']}  |  Losses: {stats['Losses']}")
    print(f"Win Rate: {stats['WinRate']}%")
    print(f"Avg Gain: +{stats['AvgGain']}%")
    print(f"Avg Loss: {stats['AvgLoss']}%")
    print("\nRecent closed trades:")
    for t in stats["Trades"][-5:]:
        print(f"  {t['Symbol']}  buy {t['BuyAvg']} → sell {t['SellPrice']}  ({t['Pct']}%)")
else:
    print("No closed trades yet.")
    print("(Log builds automatically as you add/remove from portfolio.csv)")

print("\n=== AUTO PORTFOLIO REBALANCER ===")

for row in portfolio_results:

    symbol = row["Symbol"]
    pl = row["PLPercent"]

    if pl <= -20:
        action = "EXIT"

    elif pl <= -10:
        action = "REDUCE"

    elif pl < 10:
        action = "HOLD"

    else:
        action = "ADD"

    print(symbol, "|", action)

print("\n=== PORTFOLIO ALLOCATION ===")

for index, row in portfolio.iterrows():

    symbol = row["Symbol"]
    shares = row["Shares"]
    buy_price = row["BuyPrice"]

    position_value = shares * buy_price

    allocation = round(
        (position_value / TOTAL_INVESTMENT) * 100,
        2
    )

    print(f"{symbol} : {allocation}%")
# ==================================
# UPLOAD TO SUPABASE
# ==================================

USER_ID = os.getenv("PSX_USER_ID", "default_user")

try:
    with open("psx_actions.json", "r") as f:
        actions_for_upload = json.load(f)
except Exception:
    actions_for_upload = {}

try:
    with open("psx_report.json", "r") as f:
        report_for_upload = json.load(f)
except Exception:
    report_for_upload = []

upload_to_supabase(USER_ID, actions_for_upload, report_for_upload)   
