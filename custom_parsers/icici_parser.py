import pdfplumber
import pandas as pd

def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if table:
                    header, *body = table
                    for row in body:
                        if any(cell and cell.strip() for cell in row):
                            rows.append(row)
    df = pd.DataFrame(rows, columns=["Date","Description","Debit Amt","Credit Amt","Balance"])
    for c in ["Debit Amt","Credit Amt","Balance"]:
        df[c] = pd.to_numeric(df[c].str.replace(',', ''), errors="coerce")
    return df
