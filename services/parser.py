import pdfplumber
import pandas as pd
import re
from pathlib import Path



class StatementParser:
    def __init__(self):
        self.transactions = []

    def clean_amount(self, amount):

        if amount is None:
            return 0.0

        amount = str(amount)

        # Remove PDF garbage
        amount = re.sub(r"\(cid:\d+\)", "", amount)

        amount = amount.replace("¹", "")
        amount = amount.replace("₹", "")
        amount = amount.replace(",", "")

        # Keep only digits and decimal point
        amount = re.sub(r"[^0-9.]", "", amount)

        try:
            return float(amount)
        except:
            return 0.0

    def parse_csv(self, filepath):
        df = pd.read_csv(filepath)

        transactions = []

        for _, row in df.iterrows():

            transactions.append({
                "date": str(row["Date"]),
                "merchant": str(row["Description"]).strip(),
                "amount": abs(float(row["Amount"])),
                "type": row.get("Type", "Debit")
            })

        return transactions

    def parse_pdf(self, filepath):

        transactions = []

        with pdfplumber.open(filepath) as pdf:

            for page in pdf.pages:

                tables = page.extract_tables()

                if not tables:
                    continue

                for table in tables:

                    # Skip header row
                    for row in table[1:]:

                        if not row or len(row) < 6:
                            continue

                        date = row[0]
                        merchant = row[1]

                        deposit = self.clean_amount(row[3])
                        payment = self.clean_amount(row[4])
                        balance = self.clean_amount(row[5])

                        if deposit > 0:
                            amount = deposit
                            txn_type = "Credit"
                        else:
                            amount = payment
                            txn_type = "Debit"

                        transactions.append({
                            "date": date,
                            "merchant": merchant,
                            "amount": amount,
                            "balance": balance,
                            "type": txn_type
                        })

        return transactions

    def parse(self, filepath):

        filepath = Path(filepath)

        if filepath.suffix.lower() == ".csv":
            return self.parse_csv(filepath)

        elif filepath.suffix.lower() == ".pdf":
            return self.parse_pdf(filepath)

        else:
            raise Exception("Unsupported File Format")
