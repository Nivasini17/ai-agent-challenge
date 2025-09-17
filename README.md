Bank Statement Parser Agent for ICICI

This project contains an autonomous Python agent designed to generate a custom parser for ICICI bank statement PDFs. The agent reads sample PDF and CSV files, uses an LLM API (Groq) to iteratively generate and refine a Python parser function, tests the parser output against reference CSV data, and falls back to a robust built-in parser if needed.

Features

⦁	CLI interface to specify the target bank (currently supports only icici).
⦁	Reads sample PDF bank statements and corresponding CSV reference.
⦁	Uses Groq LLM API for automated parser code generation with iterative refinement.
⦁	Tests parser output thoroughly against sample data.
⦁	Handles API rate-limiting and retries automatically.
⦁	Fallback to a built-in parser after retries fail.
⦁	Saves the final parser code for usage or further extension.

Getting Started

Python 3.7+ installed

⦁	Install required Python packages:
pip install -r requirements.txt

⦁	Set Groq API key environment variable:
export GROQ_API_KEY="your_api_key_here"

Running the Agent

Clone this repository and run the agent for ICICI bank:
python agent.py --target icici

The agent will:

⦁	Load sample files from data/icici/
⦁	Generate and test parser code up to 3 attempts
⦁	Write the parser code to custom_parsers/icici_parser.py
⦁	Use a fallback parser if needed

Folder Structure

├── agent.py                 # Main script with agent loop
├── custom_parsers/
│   └── icici_parser.py      # Generated parser saved here
├── data/
│   └── icici/
│       ├── icici_sample.pdf # Sample bank statement PDF
│       └── result.csv       # Expected CSV output
├── README.md
└── requirements.txt         # Optional: list dependencies

Contributing

Contributions and improvements are welcome! Feel free to open issues or pull requests.




