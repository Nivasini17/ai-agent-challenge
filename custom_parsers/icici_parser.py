import pdfplumber
import pandas as pd


def parse(pdf_path: str) -> pd.DataFrame:
    import pdfplumber
    import pandas as pd

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                header, *body = table
                for row in body:
                    if row:
                        row = list(row) + [''] * (5 - len(row))
                        rows.append(row[:5])

    df = pd.DataFrame(rows, columns=["Date", "Description", "Debit Amt", "Credit Amt", "Balance"])

    # Convert 'Date' to datetime, then format back to expected string format
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    df["Date"] = df["Date"].dt.strftime("%d-%m-%Y")

    for c in ["Debit Amt", "Credit Amt", "Balance"]:
        df[c] = df[c].replace(["", " "], pd.NA)
        df[c] = pd.to_numeric(df[c].str.replace(',', ''), errors="coerce")
    
    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    return df

