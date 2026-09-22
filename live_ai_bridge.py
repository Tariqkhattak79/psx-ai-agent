import json
import time
from datetime import datetime

from pypsx import TradingClient


SYMBOLS = [
    "OGDC","PPL","MARI","POL","PSO","ATRL","NRL","PRL","CNERGY","APL",

    "HUBC","KEL","KAPCO","SPWL","NPL",

    "FFC","EFERT","FATIMA","ENGRO",

    "HBL","UBL","MCB","MEBL","NBP",
    "BAFL","BAHL","AKBL","BOP","BIPL",
    "FABL","SCBPL",

    "LUCK","DGKC","MLCF","CHCC","FCCL",
    "KOHC","PIOC","BWCL","ACPL","FECTC",

    "SYS","TRG","AVN","NETSOL","OCTOPUS",

    "SEARL","AGP","HINOON","ABOT","GLAXO",
    "FEROZ","CPHL",

    "EPCL","LOTCHEM","SITC",

    "NML","GATM","KTML","ILP","NCL",
    "ADMM","GADT",

    "ISL","ASTL","MUGHAL","AGHA",
    "INIL","ASL",

    "INDU","HCAR","GHNI",
    "GHGL","MTL",

    "NATF","MUREB","UNITY","RMPL",
    "SHEZ","NESTLE",

    "AICL","EFUG","EFUL","JGICL",

    "SRVI","PAKT",

    "PAEL","WAVES",

    "BNL","GTYR","SPSL"
]


REFRESH_SECONDS = 15 * 60


def get_live_data(client):

    live_data = []

    print()
    print("================================")
    print("LIVE MARKET REFRESH")
    print("Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("================================")

    for symbol in SYMBOLS:

        try:

            quote = client.get_quote(symbol)

            record = {
                "Symbol": symbol,
                "Price": quote.get("price"),
                "Bid": quote.get("bid_price"),
                "Ask": quote.get("ask_price"),
                "Volume": quote.get("volume"),
                "High": quote.get("high"),
                "Low": quote.get("low"),
                "Change": quote.get("change"),
                "ChangePct": quote.get("change_pct"),
                "MarketState": quote.get("market_state"),
                "Timestamp": datetime.now().isoformat()
            }

            live_data.append(record)

            print(
                f"{symbol} | "
                f"Price: {record['Price']} | "
                f"State: {record['MarketState']}"
            )

        except Exception as e:

            print(f"{symbol} | ERROR: {e}")

    with open("live_market_data.json", "w") as file:

        json.dump(
            live_data,
            file,
            indent=4
        )

    print()
    print("Stocks received:", len(live_data))
    print("Live data saved.")
    print("Next refresh in 15 minutes.")


def main():

    client = TradingClient.from_env(
        paper=True
    )

    print("================================")
    print("PSX LIVE MARKET ENGINE")
    print("================================")
    print("Automatic refresh: 15 minutes")
    print("Watching:", len(SYMBOLS), "stocks")
    print("Press CTRL+C to stop.")

    while True:

        try:

            get_live_data(client)

            time.sleep(
                REFRESH_SECONDS
            )

        except KeyboardInterrupt:

            print()
            print(
                "Live Market Engine stopped."
            )
            break

        except Exception as e:

            print()
            print(
                "Engine error:",
                e
            )

            print(
                "Retrying in 30 seconds..."
            )

            time.sleep(30)


if __name__ == "__main__":

    main()