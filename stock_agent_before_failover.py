import yfinance as yf
import pandas as pd
import json

portfolio = pd.read_csv("portfolio.csv")

with open("live_market_data.json", "r") as file:
    live_market_data = json.load(file)

live_price_map = {
    row["Symbol"]: row["Price"]
    for row in live_market_data
    if row.get("Price") is not None
}
portfolio_results = []
import smtplib
from email.message import EmailMessage

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

    try:
        data = yf.Ticker(symbol + ".KA").history(period="1y")

        if len(data) == 0:
            continue

    except Exception:
        continue

    if len(data) < 50:
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
        "Target2": target2
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

print("\n=== PSX STOCK RANKING ===")
print(df)

print("\n=== ELITE WATCHLIST (TOP 10) ===")

elite_entries = df[
    (df["OpportunityScore"] >= 70)
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
sender_email = "soeffort1@gmail.com"
app_password = "ingl fhia tydk auki"

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

    try:
        data = yf.Ticker(symbol + ".KA").history(period="5d")

        if len(data) == 0:
            print(symbol, "No market data")
            continue

    except Exception:
        print(symbol, "No market data")
        continue

    current_price = round(data["Close"].iloc[-1], 2)

    
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

    total_investment += investment
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
print("\n=== PORTFOLIO SUMMARY ===")

portfolio_pl = round(
    ((total_current_value - total_investment)
    / total_investment) * 100,
    2
)

print("Total Investment:", round(total_investment, 2))
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
print("\n=== PORTFOLIO ALLOCATION ===")

for index, row in portfolio.iterrows():

    symbol = row["Symbol"]
    shares = row["Shares"]
    buy_price = row["BuyPrice"]

    position_value = shares * buy_price

    allocation = round(
        (position_value / total_investment) * 100,
        2
    )

    print(
        f"{symbol} : {allocation}%"
    )
   