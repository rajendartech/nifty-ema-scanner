# NIFTY EMA Scanner

A desktop stock scanner for the Indian stock market (NSE) that runs locally. It scans NIFTY stocks in real-time, displays BUY/SELL signals based on custom technical criteria, and provides visual charts and alerts.

## Project Structure
```text
nifty_ema_scanner/
│
├── app.py              # Main Streamlit dashboard application
├── scanner.py          # Data fetching and indicator logic processing
├── symbols.py          # Predefined lists of NSE symbols (NIFTY50, NIFTY100, etc.)
├── requirements.txt    # Python dependencies
└── README.md           # Instructions for setup
```

## Prerequisites

- Python 3.9+
- Windows OS (for sound alerts)

## Installation

1. Open your terminal or powershell in this project directory.
2. It's recommended to create a virtual environment:
   ```bash
   python -m venv venv
   ## Activate the virtual environment:
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the App

Run the following command in your terminal:
```bash
streamlit run app.py
```
This will automatically open the dashboard in your default web browser (usually accessible at http://localhost:8501).

## Features
- **Real-Time Scanning:** Automatically scans stocks every configurable interval (e.g. 5 mins).
- **Customizable EMAs:** Tweak fast and slow EMA values from the settings sidebar.
- **Desktop Alerts:** Triggers native Windows notifications and a beep sound on new signals.
- **Charts:** Built-in rich Plotly Candlestick charts to instantly verify signals.
- **Timeframes:** Evaluates 5m interval for EMA crossover, filtered by Daily timeframe previous-day-high breakouts, and moving average trends.
