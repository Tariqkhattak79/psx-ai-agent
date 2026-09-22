import yfinance as yf
import pandas as pd

symbol = "HBL.KA"

data = yf.Ticker(symbol).history(period="1y")

data["MA20"] = data["Close"].rolling(20).mean()
data["MA50"] = data["Close"].rolling(50).mean()

delta = data["Close"].diff()

gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss

data["RSI"] = 100 - (100 / (1 + rs))

trades = []

for i in range(50, len(data) - 5):

    row = data.iloc[i]

    score = 0

    if row["Close"] > row["MA20"]:
        score += 1

    if row["MA20"] > row["MA50"]:
        score += 1

    if score >= 2 and row["RSI"] < 70:

        buy_price = row["Close"]

        sell_price = data.iloc[i + 5]["Close"]

        profit_pct = (
            (sell_price - buy_price)
            / buy_price
        ) * 100

        trades.append(profit_pct)

print("Total Trades:", len(trades))

if len(trades) > 0:

    winners = [t for t in trades if t > 0]

    win_rate = len(winners) / len(trades) * 100

    avg_profit = sum(trades) / len(trades)

    best_trade = max(trades)

    worst_trade = min(trades)

    total_return = sum(trades)

    print("Win Rate:", round(win_rate, 2), "%")
    print("Average Profit:", round(avg_profit, 2), "%")
    print("Best Trade:", round(best_trade, 2), "%")
    print("Worst Trade:", round(worst_trade, 2), "%")
    print("Total Return:", round(total_return, 2), "%")