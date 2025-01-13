import typer
from datetime import datetime
from datetime import timedelta
import asyncio
from typing import Optional
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

from src.garmin_client import GarminClient
from src.sheets_client import GoogleSheetsClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

@app.command()
def sync_wrapper(
    start_date: datetime = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end_date: datetime = typer.Option(..., help="End date (YYYY-MM-DD)"),
    email: Optional[str] = typer.Option(None, help="Garmin Connect email"),
    password: Optional[str] = typer.Option(None, help="Garmin Connect password"),
    sheets_id: Optional[str] = typer.Option(None, help="Google Sheets ID")
):
    """
    Sync Garmin Connect data to Google Sheets for the specified date range
    """
    asyncio.run(sync(start_date, end_date, email, password, sheets_id))

async def sync(
    start_date: datetime,
    end_date: datetime,
    email: Optional[str],
    password: Optional[str],
    sheets_id: Optional[str]
):
    try:
        # Load environment variables
        load_dotenv()
        
        # Get credentials from env vars if not provided as arguments
        email = email or os.getenv("GARMIN_EMAIL")
        password = password or os.getenv("GARMIN_PASSWORD")
        sheets_id = sheets_id or os.getenv("GOOGLE_SHEETS_ID")

        logger.info("Credentials loaded")
        logger.info(f"Using Google Sheets ID: {sheets_id}")

        if not all([email, password, sheets_id]):
            raise typer.BadParameter(
                "Missing required credentials. Provide them as arguments or environment variables."
            )

        logger.info("Initializing Garmin client...")
        garmin_client = GarminClient(email, password)
        
        logger.info("Initializing Google Sheets client...")

        # Use environment variables for Google credentials path
        credentials_dir = os.getenv('GOOGLE_CREDENTIALS_DIR', 'credentials')
        client_secret_file = os.getenv('GOOGLE_CLIENT_SECRET_FILE', 'client_secret.json')
        credentials_path = str(Path(credentials_dir) / client_secret_file)

        sheets_client = GoogleSheetsClient(
            credentials_path=credentials_path,
            spreadsheet_id=sheets_id
        )

        logger.info(f"Starting sync from {start_date} to {end_date}")
        
        # Convert start_date and end_date to date objects if they aren't already
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date
        
        # Authenticate with Garmin
        logger.info("Authenticating with Garmin...")
        await garmin_client.authenticate()
        
        # Get metrics for each day in the date range
        metrics = []
        current_date = start
        while current_date <= end:
            logger.info(f"Fetching metrics for {current_date}")
            daily_metrics = await garmin_client.get_metrics(current_date)
            metrics.append(daily_metrics)
            current_date += timedelta(days=1)
            
        # Update Google Sheet with the metrics
        logger.info("Updating Google Sheet...")
        sheets_client.update_metrics(metrics)
        
        logger.info("Sync completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    app()