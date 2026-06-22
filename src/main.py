import pandas as pd
from datetime import datetime, timedelta

def normalise_date(val):
    # Excel serial number (e.g. 46142)
    if isinstance(val, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=int(val))).strftime("%Y-%m-%d")
    # String date (e.g. "25-04-2026" or "30/04/2026")
    if isinstance(val, str):
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return str(val)

# Load the Excel file
df = pd.read_excel("C:\\Users\\AKKU\\OneDrive\\文档\\GitHub\\cdproject\\april_2026_offers.xlsx")

# Normalise dates
df["offer_valid_to"] = df["offer_valid_to"].apply(normalise_date)

# Print results
print(df.to_string(index=False))
