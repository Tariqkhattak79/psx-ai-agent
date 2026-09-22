import asyncio
from pypsx import TradingClient


SYMBOLS = [
    "OGDC",
    "HBL",
    "PSO",
    "LUCK",
    "SYS"
]


async def watch_symbol(client, symbol):

    while True:

        try:

            print(f"{symbol} | Connecting...")

            async for tick in client.stream_ticker(symbol):

                print(
                    f"{symbol} | "
                    f"Price: {tick.get('p')} | "
                    f"Bid: {tick.get('b')} | "
                    f"Ask: {tick.get('a')} | "
                    f"Volume: {tick.get('v')} | "
                    f"Time: {tick.get('t')}"
                )

        except Exception as e:

            print(f"{symbol} | Connection lost: {e}")
            print(f"{symbol} | Reconnecting in 5 seconds...")

            await asyncio.sleep(5)


async def main():

    client = TradingClient.from_env(paper=True)

    print("================================")
    print("PSX STABLE LIVE MARKET STREAM")
    print("================================")
    print("Watching:", ", ".join(SYMBOLS))
    print("Automatic reconnect: ON")
    print("Press CTRL+C to stop.")
    print()

    tasks = []

    for symbol in SYMBOLS:

        tasks.append(
            asyncio.create_task(
                watch_symbol(client, symbol)
            )
        )

    await asyncio.gather(*tasks)


try:

    asyncio.run(main())

except KeyboardInterrupt:

    print()
    print("Live market stream stopped.")