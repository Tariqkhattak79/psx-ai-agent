import yfinance as yf
import pandas as pd
portfolio = pd.read_csv("portfolio.csv")
portfolio_results = []
import smtplib
from email.message import EmailMessage

symbols = [
    "OGDC",
    "PPL",
    "MARI",
    "HUBC",
    "FFC",
    "ENGRO",
    "LUCK",
    "HBL",
    "UBL",
    "MCB",
    "PSO",
    "SYS",
    "TRG",
    "EFERT",
    "POL"
]
results = []

for symbol in symbols:

    data = yf.Ticker(symbol + ".KA").history(period="3mo")

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

    latest = data.iloc[-1]
    rsi = latest["RSI"]

    avg_volume = data["Volume"].rolling(20).mean().iloc[-1]
    current_volume = latest["Volume"]

    highest_20 = data["High"].tail(20).max()

    breakout = latest["Close"] > highest_20

    score = 0

    if latest["Close"] > latest["MA20"]:
        score += 1

    if latest["MA20"] > latest["MA50"]:
        score += 1
    if current_volume > avg_volume:
        score += 1
    if breakout:
        score += 1

    if score >= 2 and rsi < 70:
        signal = "BUY"
    elif rsi < 30:
        signal = "WATCH"
    elif score == 1:
        signal = "HOLD"
    else:
        signal = "SELL"

    buy_price = round(latest["Close"], 2)

    stop_loss = round(buy_price * 0.95, 2)

    target1 = round(buy_price * 1.08, 2)

    target2 = round(buy_price * 1.15, 2)

    results.append({
        "Symbol": symbol,
        "Close": buy_price,
        "RSI": round(rsi, 2),
        "Score": score,
        "Signal": signal,
        "StopLoss": stop_loss,
        "Target1": target1,
        "Target2": target2
    })

df = pd.DataFrame(results)

df = df.sort_values("Score", ascending=False)

print("\n=== PSX STOCK RANKING ===")
print(df)
print("\n=== TOP OPPORTUNITIES ===")

top = df.sort_values(["Score", "RSI"], ascending=[False, True])

print(top[["Symbol", "RSI", "Signal"]].head(3))
df.to_excel("psx_report.xlsx", index=False)

print("\nReport saved as psx_report.xlsx")
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
print("\n=== MY PORTFOLIO ===")

for index, row in portfolio.iterrows():

    symbol = row["Symbol"]
    buy_price = row["BuyPrice"]

    try:
        data = yf.Ticker(symbol + ".KA").history(period="5d")

        if len(data) == 0:
            print(symbol, "No market data")
            continue

    except Exception:
        print(symbol, "No market data")
        continue

    current_price = round(data["Close"].iloc[-1], 2)

    profit_pct = round(
        ((current_price - buy_price) / buy_price) * 100,
        2
    )

    if profit_pct > 5:
        action = "TAKE PROFIT"

    elif profit_pct > -5:
        action = "HOLD"

    elif profit_pct > -15:
        action = "REVIEW"

    else:
        action = "EXIT CANDIDATE"

    print(
        symbol,
        "Buy:", buy_price,
        "Current:", current_price,
        "P/L:", str(profit_pct) + "%",
        "Action:", action
    )