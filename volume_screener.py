import yfinance as yf
import pandas as pd
import requests
import numpy as np
import datetime

# --- CONFIG ---
TICKERS = [
    "AAPL", "AMD", "AMZN", "AVGO", "BABA", "BRK.B", "COST", "CRWV", "GOOGL",
    "JNJ", "JPM", "KO", "LLY", "META", "MSFT", "NFLX", "NVDA", "ORCL", "PG",
    "PLTR", "QQQ", "RDDT", "SPY", "TSLA", "TSM", "UNH", "V", "WMT", "XOM"
]

# Volume Screener Specific Configuration
VOLUME_AVERAGE_PERIOD = 50  # Days for calculating average volume
VOLUME_MULTIPLIER = 2.0     # Today's volume must be at least this many times the average
MIN_AVG_VOLUME = 1_000_000  # Minimum 50-day average volume for a stock to be considered
MIN_CLOSE_PRICE = 5.0       # Minimum current closing price for a stock to be considered

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1389683227886882888/WS5YJSmGZtQb9zLtVfipeKoHArMa-IWMfxrcYLUBiPRmdkRU7lAskoW9K33aUdP8MfOS"  # replace with yours

def fetch_data(ticker):
    """
    Fetches historical data for a given ticker, including Close price and Volume.
    Calculates the Simple Moving Average (SMA) of the Volume.
    """
    # Fetch enough data for the EMA calculation + the volume average period
    # Using 100 days to be safe for a 50-day average.
    df = yf.download(ticker, period="100d", interval="1d", threads=False, auto_adjust=True)
    
    # Calculate the SMA of the Volume
    if not df.empty and 'Volume' in df.columns:
        df[f'Volume_SMA{VOLUME_AVERAGE_PERIOD}'] = df['Volume'].rolling(window=VOLUME_AVERAGE_PERIOD).mean()
    else:
        print(f"Warning: No 'Volume' column or empty dataframe for {ticker}.")
    return df

def check_volume_spike(ticker):
    """
    Checks if a stock has experienced a significant volume spike today
    based on the defined criteria.
    """
    df = fetch_data(ticker)

    # Basic data validation
    if df.empty or 'Close' not in df.columns or 'Volume' not in df.columns or \
       f'Volume_SMA{VOLUME_AVERAGE_PERIOD}' not in df.columns:
        print(f"Skipping {ticker}: Dataframe is empty or missing required columns.")
        return None

    # Ensure there's enough data for the average calculation and today's data
    if len(df) < VOLUME_AVERAGE_PERIOD + 1: # Need at least X days for SMA + current day
        print(f"Skipping {ticker}: Not enough historical data for volume average calculation. (Rows: {len(df)})")
        return None

    latest_data = df.iloc[-1]
    
    # Extract scalar values using .item() for robustness
    try:
        today_close = latest_data['Close'].item()
        today_volume = latest_data['Volume'].item()
        avg_volume = latest_data[f'Volume_SMA{VOLUME_AVERAGE_PERIOD}'].item()
    except (ValueError, KeyError) as e:
        print(f"Skipping {ticker}: Could not extract scalar values for Close, Volume, or Avg Volume. Error: {e}")
        return None

    # Check for NaN values in critical metrics
    if pd.isna(today_close) or pd.isna(today_volume) or pd.isna(avg_volume):
        print(f"Skipping {ticker}: Latest Close, Volume, or Average Volume is NaN. "
              f"(Close: {today_close}, Volume: {today_volume}, Avg Volume: {avg_volume})")
        return None

    # Apply filtering criteria
    if avg_volume < MIN_AVG_VOLUME:
        print(f"Skipping {ticker}: Average volume ({avg_volume:.0f}) is below minimum threshold ({MIN_AVG_VOLUME:.0f}).")
        return None
    
    if today_close < MIN_CLOSE_PRICE:
        print(f"Skipping {ticker}: Close price ({today_close:.2f}) is below minimum threshold ({MIN_CLOSE_PRICE:.2f}).")
        return None

    # Check for volume spike
    if avg_volume > 0 and today_volume >= (avg_volume * VOLUME_MULTIPLIER):
        volume_ratio = round(today_volume / avg_volume, 2)
        return (f"VOLUME ALERT: {ticker} volume is {volume_ratio}x its {VOLUME_AVERAGE_PERIOD}-day average! "
                f"(Today's Volume: {today_volume:.0f}, Avg Volume: {avg_volume:.0f}, Close: {today_close:.2f})")
    
    return None

def send_discord_alert(message):
    """
    Sends a message to the configured Discord webhook.
    """
    data = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK, json=data)
        print(f"Discord alert sent with status code: {response.status_code}")
        if not response.ok:
            print(f"ERROR: Discord webhook failed with status code {response.status_code}: {response.text}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to send Discord alert due to network or request error: {e}")
        return None

def run_volume_screener():
    """
    Main function to run the volume screener for all configured tickers.
    """
    print(f"Running Volume Screener at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    found_alerts = False
    for ticker in TICKERS:
        alert = check_volume_spike(ticker)
        if alert:
            print(alert)
            send_discord_alert(alert)
            found_alerts = True
    
    if not found_alerts:
        print("No significant volume spikes found today.")
        send_discord_alert("Daily Volume Screener: No significant volume spikes found today.") # Optional: send a "no alerts" message

if __name__ == "__main__":
    run_volume_screener()
