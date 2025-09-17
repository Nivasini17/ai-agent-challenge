python
import pandas as pd
import PyPDF2
import re

def parse(pdf_path: str) -> pd.DataFrame:
    """
    Parse a bank statement PDF and return a DataFrame with cleaned data.

    Args:
    pdf_path (str): Path to the PDF file.

    Returns:
    pandas.DataFrame: A DataFrame with columns [Date, Description, Debit Amt, Credit Amt, Balance].
    """

    # Open the PDF file and read its contents
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()

    # Split the text into lines
    lines = text.split('\n')

    # Remove empty lines
    lines = [line for line in lines if line.strip()]

    # Initialize variables to store the data
    data = []
    date = None
    description = None
    debit_amt = None
    credit_amt = None
    balance = None

    # Iterate over the lines to extract the data
    for line in lines:
        # Remove leading and trailing whitespace
        line = line.strip()

        # Check if the line contains a date
        if re.match(r'\d{2}-\d{2}-\d{4}', line):
            date = line
        # Check if the line contains a description
        elif line.startswith('Date'):
            continue
        elif line.startswith('Description'):
            description = line.replace('Description', '').strip()
        # Check if the line contains a debit amount
        elif line.startswith('Debit'):
            debit_amt = line.replace('Debit', '').strip()
        # Check if the line contains a credit amount
        elif line.startswith('Credit'):
            credit_amt = line.replace('Credit', '').strip()
        # Check if the line contains a balance
        elif line.startswith('Balance'):
            balance = line.replace('Balance', '').strip()
        # If the line contains a number, it's likely a debit or credit amount
        elif re.match(r'\d+\.\d+', line):
            if debit_amt is None:
                debit_amt = line
            else:
                credit_amt = line

        # If we've found all the necessary information, add it to the data
        if date and description and debit_amt and credit_amt and balance:
            data.append({
                'Date': date,
                'Description': description,
                'Debit Amt': debit_amt.replace(',', ''),
                'Credit Amt': credit_amt.replace(',', ''),
                'Balance': balance.replace(',', '')
            })
            # Reset the variables to extract the next set of data
            date = None
            description = None
            debit_amt = None
            credit_amt = None
            balance = None

    # Create a DataFrame from the data
    df = pd.DataFrame(data)

    # Convert the columns to the correct data types
    df['Date'] = pd.to_datetime(df['Date'])
    df['Debit Amt'] = pd.to_numeric(df['Debit Amt'])
    df['Credit Amt'] = pd.to_numeric(df['Credit Amt'])
    df['Balance'] = pd.to_numeric(df['Balance'])

    return df
```

This function uses the `PyPDF2` library to read the PDF file and extract its text. It then splits the text into lines and iterates over them to extract the date, description, debit amount, credit amount, and balance. The data is stored in a list of dictionaries, which is then converted to a pandas DataFrame. The columns are converted to the correct data types using `pd.to_datetime` and `pd.to_numeric`.