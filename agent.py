import os
import sys
import argparse
import pandas as pd
import requests
import time
import re
import pdfplumber
from functools import lru_cache


DATA_DIR = os.path.join("data", "icici")
PDF_FILE = os.path.join(DATA_DIR, "icici_sample.pdf")
CSV_FILE = os.path.join(DATA_DIR, "result.csv")
PARSER_PATH = os.path.join("custom_parsers", "icici_parser.py")


GROQ_API_URL_BASE = "https://api.groq.com/openai/v1"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("Groq API key not set. Use environment variable GROQ_API_KEY.")


HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}


def get_available_models():
    url = f"{GROQ_API_URL_BASE}/models"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", [])]


def select_groq_model(preferred=None):
    models = get_available_models()
    print(f"[INFO] Available Groq models: {models}")
    if preferred:
        for m in preferred:
            if m in models:
                print(f"[INFO] Using preferred model: {m}")
                return m
    return "llama-3.1-8b-instant" if "llama-3.1-8b-instant" in models else (models[0] if models else None)


def call_llm_api(prompt: str, model: str, max_retries=3) -> str:
    api_url = f"{GROQ_API_URL_BASE}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert Python developer."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.1
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(api_url, headers=HEADERS, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            if resp.status_code == 429:
                wait = int(resp.headers.get("retry-after", 0)) or (2 ** attempt) * 5
                print(f"[WARN] Rate limit exceeded. Retrying in {wait} seconds...")
                time.sleep(wait)
                continue
            raise
        except Exception:
            raise
    raise RuntimeError("Failed to get response from Groq API after retries.")


def clean_code(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"\`\`\`(?:python)?\s*([\s\S]+?)\s*\`\`\`", raw, re.IGNORECASE)
    if m:
        code = m.group(1)
        lines = code.splitlines()
        if lines and (lines[0].strip().lower() == "python" or lines[0].strip().startswith(("$", "!", "%"))):
            lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines).strip()
    return raw.strip("` \n\r\t")


def fix_pdfplumber_imports(code: str) -> str:
    code = code.replace("from pdfplumber import pdf", "import pdfplumber")
    code = code.replace("from pdfplumber import open as pdf_open", "import pdfplumber")
    code = re.sub(r"(\b)pdf\.open\(", r"\1pdfplumber.open(", code)
    return code


def is_syntax_valid(code_str: str) -> bool:
    try:
        compile(code_str, "<string>", "exec")
        return True
    except SyntaxError as e:
        print(f"[ERROR] Syntax error in generated code: {e}")
        lines = code_str.splitlines()
        lineno = e.lineno - 1 if e.lineno else None
        if lineno is not None and 0 <= lineno < len(lines):
            start = max(0, lineno - 2)
            end = min(len(lines), lineno + 3)
            print("Code snippet with error:")
            for i in range(start, end):
                prefix = ">>" if i == lineno else "  "
                print(f"{prefix} {lines[i]}")
        return False


@lru_cache(maxsize=1)
def extract_pdf_summary(pdf_path: str, max_pages=2) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            txt = page.extract_text()
            if txt:
                texts.append(txt.strip())
    return "\n".join(texts)


def get_csv_sample(csv_path: str, max_lines=10):
    with open(csv_path, "r", encoding="utf-8") as f:
        for _ in range(max_lines):
            yield next(f, "")


def generate_parser_code(pdf_summary: str, csv_sample: str, feedback: str, model: str) -> str:
    prompt = f"""
You must write a valid complete Python function named `parse(pdf_path: str) -> pd.DataFrame` that:
- Parses bank statement tables or text using pdfplumber.
- Returns a pandas DataFrame with columns Date, Description, Debit Amt, Credit Amt, Balance.
- Properly cleans and safely converts numeric columns.
- Skips repeated headers and empty rows.
- Handles rows with missing columns gracefully by filling with empty strings.
- Drops rows where Date cannot be parsed.
- Uses 'pdfplumber.open(...)' correctly.
- Does NOT include any import statements, comments, explanations, or markdown.
- Uses Python 3.8+ syntax, runnable and self-contained.
- Refers to pandas as 'pd' (consistent with import aliasing).
- Does NOT include the word 'python' or any special command lines in output.
- Uses regex to split lines with multi-word descriptions correctly.

Example safe parsing logic you must follow (do NOT copy imports or comments):

def parse(pdf_path: str) -> pd.DataFrame:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    lines = [line.strip() for line in text.split("\\n") if line.strip()]
    headers = [line for line in lines if "Date" in line and "Description" in line]
    if headers:
        header_line = headers[0]
        lines = [line for line in lines if line != header_line]

    import re
    data = []
    for line in lines:
        m = re.match(r"^(\\d{{2}}-\\d{{2}}-\\d{{4}})\\s+(.*?)\\s+(\\d*[\\.,]?\\d*)\\s+(\\d*[\\.,]?\\d*)\\s+(\\d*[\\.,]?\\d*)$", line)
        if m:
            date, desc, debit, credit, balance = m.groups()
            data.append([date, desc, debit, credit, balance])

    df = pd.DataFrame(data, columns=["Date", "Description", "Debit Amt", "Credit Amt", "Balance"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True, format="%d-%m-%Y")
    for col in ["Debit Amt", "Credit Amt", "Balance"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce").fillna(0.0)

    return df.dropna(subset=["Date"])

Given this sample bank statement text:
{pdf_summary}

Given expected CSV sample:
{"".join(csv_sample)}

Previous feedback:
{feedback}

Return only the complete function code (no extra text).
"""
    raw_code = call_llm_api(prompt, model)
    # Suppressed raw code output for cleanliness
    return raw_code


def write_parser(code: str):
    cleaned = clean_code(code)
    cleaned = cleaned.replace("pandas.", "pd.")  # Replace pandas with pd alias
    cleaned = fix_pdfplumber_imports(cleaned)
    if is_syntax_valid(cleaned):
        os.makedirs(os.path.dirname(PARSER_PATH), exist_ok=True)
        with open(PARSER_PATH, "w", encoding="utf-8") as f:
            f.write(cleaned)
    else:
        raise SyntaxError("Generated parser code failed syntax validation.")


def write_fallback_parser():
    fallback = '''\
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

'''
    os.makedirs(os.path.dirname(PARSER_PATH), exist_ok=True)
    with open(PARSER_PATH, "w", encoding="utf-8") as f:
        f.write(fallback)


def test_parser():
    import importlib.util
    import pandas as pd
    import pdfplumber

    spec = importlib.util.spec_from_file_location("parser", PARSER_PATH)
    module = importlib.util.module_from_spec(spec)

    # Inject pandas and pdfplumber modules into parser module
    module.__dict__['pd'] = pd
    module.__dict__['pdfplumber'] = pdfplumber

    spec.loader.exec_module(module)

    df_parsed = module.parse(PDF_FILE)
    df_ref = pd.read_csv(CSV_FILE)

    cols = ["Date", "Description", "Debit Amt", "Credit Amt", "Balance"]
    df_parsed = df_parsed.reindex(columns=cols).fillna(pd.NA).reset_index(drop=True)
    df_ref = df_ref.reindex(columns=cols).fillna(pd.NA).reset_index(drop=True)

    print("\nParsed sample:\n", df_parsed.head())
    print("\nReference sample:\n", df_ref.head())

    try:
        diff = df_ref.compare(df_parsed)
        if not diff.empty:
            print("\nDifferences:\n", diff)
            return False, str(diff)
    except Exception:
        pass
    return df_ref.equals(df_parsed), ""


def agent_loop():
    model = select_groq_model(preferred=["llama-3.1-8b-instant", "llama-3.3-70b-versatile"])
    if not model:
        print("[ERROR] No valid Groq model found.")
        sys.exit(1)

    pdf_summary = extract_pdf_summary(PDF_FILE)
    csv_sample = list(get_csv_sample(CSV_FILE))
    feedback = ""

    for attempt in range(1, 4):
        print(f"\nAgent attempt {attempt}")
        try:
            code = generate_parser_code(pdf_summary, csv_sample, feedback, model)
            if not is_syntax_valid(clean_code(code)):
                print("[WARN] Generated code syntax invalid, retrying...")
                feedback = "Syntax error in generated parser code."
                continue
            write_parser(code)
            passed, feedback = test_parser()
            if passed:
                print("✅ Parser passed the test!")
                return
            print("❌ Parser failed the test. Feedback used for refinement.")
        except Exception as e:
            print(f"[ERROR] Exception during attempt {attempt}: {e}")
        time.sleep(1)

    print("[WARN] Using fallback parser due to failures...")
    write_fallback_parser()
    passed, _ = test_parser()
    print("✅ Fallback parser passed the test!" if passed else "❌ Fallback parser failed.")
    print("⚠️ Agent failed to build a working parser after max attempts.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, help="Target bank (e.g., icici)")
    args = p.parse_args()
    if args.target.lower() != "icici":
        print("Only 'icici' target supported currently.")
        sys.exit(1)
    agent_loop()


if __name__ == "__main__":
    main()
