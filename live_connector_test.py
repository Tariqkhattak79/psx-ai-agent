import json

print("================================")
print("LIVE DATA → AI CONNECTOR TEST")
print("================================")
print()

with open("live_market_data.json", "r") as file:
    live_data = json.load(file)

print("Stocks received:", len(live_data))
print()

for row in live_data:

    print(
        f"{row['Symbol']} | "
        f"Live Price: {row['Price']} | "
        f"Volume: {row['Volume']} | "
        f"Market: {row['MarketState']}"
    )

print()
print("LIVE DATA → AI CONNECTOR TEST COMPLETE")