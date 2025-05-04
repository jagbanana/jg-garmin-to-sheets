import typer
import sys # Added for exiting
from datetime import datetime, timedelta, date # Ensure date is imported
import asyncio
from typing import Optional
import os
from pathlib import Path # Added import
from dotenv import load_dotenv
import logging

from src.garmin_client import GarminClient
from src.sheets_client import GoogleSheetsClient, GoogleAuthTokenRefreshError # Added import
import re # Added for regex matching

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

@app.command()
def sync_wrapper():
    """
    Sync Garmin Connect data to Google Sheets. Prompts for user profile and date range.
    """
    asyncio.run(sync())

async def sync():
    try:
        # Load environment variables
        load_dotenv()

        # Load user profiles from environment variables
        user_profiles = load_user_profiles()
        logger.info(f"Loaded {len(user_profiles)} user profiles: {list(user_profiles.keys())}")

        # Check if profiles exist
        if not user_profiles:
            logger.error("No user profiles found in .env file. Please define at least one profile (e.g., USER1_GARMIN_EMAIL=...).")
            sys.exit(1) # Exit if no profiles

        # --- Profile Selection ---
        profile_names = list(user_profiles.keys())
        print("\nAvailable User Profiles:")
        for i, name in enumerate(profile_names):
            print(f"{i + 1}. {name}")

        selected_profile_index = -1
        while True:
            try:
                choice = input(f"Select profile number (1-{len(profile_names)}): ")
                selected_profile_index = int(choice) - 1
                if 0 <= selected_profile_index < len(profile_names):
                    break
                else:
                    print("Invalid choice. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        selected_profile_name = profile_names[selected_profile_index]
        selected_profile_data = user_profiles[selected_profile_name]
        email = selected_profile_data['email']
        password = selected_profile_data['password']
        sheets_id = selected_profile_data['sheet_id']
        logger.info(f"Using profile: {selected_profile_name}")

        # --- Date Input ---
        date_format = "%Y-%m-%d"
        start_date: Optional[date] = None
        end_date: Optional[date] = None

        while True:
            try:
                start_date_str = input(f"Enter start date ({date_format}): ")
                start_date = datetime.strptime(start_date_str, date_format).date() # Store as date object
                break
            except ValueError:
                print(f"Invalid date format. Please use {date_format}.")

        while True:
            try:
                end_date_str = input(f"Enter end date ({date_format}): ")
                end_date = datetime.strptime(end_date_str, date_format).date() # Store as date object
                if end_date >= start_date:
                    break
                else:
                    print("End date cannot be before start date.")
            except ValueError:
                print(f"Invalid date format. Please use {date_format}.")

        # Initialize Garmin client
        logger.info("Initializing Garmin client...")
        garmin_client = GarminClient(email, password)

        logger.info(f"Starting sync from {start_date.strftime(date_format)} to {end_date.strftime(date_format)}")

        # Authenticate with Garmin
        logger.info("Authenticating with Garmin...")
        await garmin_client.authenticate()

        # Get metrics for each day in the date range
        logger.info("Fetching metrics from Garmin...")
        metrics = []
        current_date = start_date # Use validated start_date
        end = end_date           # Use validated end_date
        while current_date <= end:
            logger.info(f"Fetching metrics for {current_date}")
            daily_metrics = await garmin_client.get_metrics(current_date)
            metrics.append(daily_metrics)
            current_date += timedelta(days=1)

        # Initialize Google Sheets client and update sheet (within inner try/except)
        try:
            logger.info("Initializing Google Sheets client...")
            sheets_client = GoogleSheetsClient(
                credentials_path='credentials/client_secret.json',
                spreadsheet_id=sheets_id
            )

            logger.info("Updating Google Sheet...")
            sheets_client.update_metrics(metrics)

            logger.info("Sync completed successfully!")

        except GoogleAuthTokenRefreshError as auth_error:
            logger.warning(f"Google authentication error: {auth_error}")
            print("\n" + "="*30)
            print(" Google Authentication Issue")
            print("="*30)
            response = input("Google authentication token.pickle may be expired or invalid.\nDo you want to delete it and re-authenticate on the next run? [Y/N]: ").strip().lower()

            if response == 'y':
                logger.info("User chose to re-authenticate. Deleting token.pickle...")
                token_path = Path('credentials/token.pickle')
                if token_path.exists():
                    try:
                        token_path.unlink()
                        logger.info(f"Deleted token file: {token_path}")
                        print(f"\nToken file ({token_path}) has been removed.")
                        print("Please re-run the application to re-authenticate with Google.")
                    except OSError as e:
                        logger.error(f"Error deleting token file {token_path}: {e}")
                        print(f"\nError deleting token file: {e}. Please delete it manually and re-run.")
                else:
                    logger.warning(f"Token file not found at {token_path}, cannot delete.")
                    print("\nToken file not found. Please re-run the application to authenticate.")
                sys.exit(0) # Exit gracefully after handling token deletion
            else:
                logger.info("User chose not to re-authenticate.")
                print("\nAuthentication is required to update Google Sheets. Exiting.")
                sys.exit(1) # Exit with error code as user declined

    # This is the general exception handler for the outer try block (starting line 29)
    except Exception as e:
        logger.error(f"An unexpected error occurred during the sync process: {str(e)}", exc_info=True) # Log traceback
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1) # Exit with error code for general errors

def load_user_profiles():
    """
    Parses environment variables to find and structure user profiles.
    Looks for variables like USER<N>_GARMIN_EMAIL, USER<N>_GARMIN_PASSWORD, USER<N>_SHEET_ID.
    """
    profiles = {}
    # Regex to match USER<N>_ followed by the credential type
    profile_pattern = re.compile(r"^(USER\d+)_(GARMIN_EMAIL|GARMIN_PASSWORD|SHEET_ID)$")

    for key, value in os.environ.items():
        match = profile_pattern.match(key)
        if match:
            profile_name = match.group(1) # e.g., "USER1"
            var_type = match.group(2)     # e.g., "GARMIN_EMAIL"

            if profile_name not in profiles:
                profiles[profile_name] = {}

            # Map the env var type to a simpler key in the profile dict
            if var_type == "GARMIN_EMAIL":
                profiles[profile_name]['email'] = value
            elif var_type == "GARMIN_PASSWORD":
                profiles[profile_name]['password'] = value
            elif var_type == "SHEET_ID":
                profiles[profile_name]['sheet_id'] = value

    # Filter out incomplete profiles (missing any of the three required fields)
    complete_profiles = {}
    for name, data in profiles.items():
        if 'email' in data and 'password' in data and 'sheet_id' in data:
            complete_profiles[name] = data
        else:
            logger.warning(f"Ignoring incomplete profile '{name}': missing required fields.")

    return complete_profiles


if __name__ == "__main__":
    app()