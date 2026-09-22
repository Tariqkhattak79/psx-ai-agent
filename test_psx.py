import psxdata
df = psxdata.stocks("ENGRO", start="2025-01-01", end="2026-09-20")
print(len(df))
print(df.tail())
