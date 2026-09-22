import json
from datetime import datetime

print("=" * 40)
print("PSX BACKUP MARKET SOURCE")
print("=" * 40)

backup_data = {
    "Source": "Backup",
    "Timestamp": datetime.now().isoformat(),
    "Status": "READY"
}

with open("backup_market_data.json", "w") as f:
    json.dump(
        backup_data,
        f,
        indent=4
    )

print("Backup source file created.")
print("backup_market_data.json saved.")