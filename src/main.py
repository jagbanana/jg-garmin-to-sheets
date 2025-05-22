import typer
import sys # Added for exiting
from datetime import datetime, timedelta, date # Ensure date is imported
import asyncio
from typing import Optional
import os
import csv # Added for CSV output
import subprocess # Added for opening directory
from pathlib import Path # Added import
from dotenv import load_dotenv
import logging

from src.garmin_client import GarminClient
from src.sheets_client import GoogleSheetsClient, GoogleAuthTokenRefreshError # Added import
import re # Added for regex matching
from garth.exc import GarthHTTPError # Import the specific Garmin error


# --- Constants ---
CSV_HEADERS = [
    "Date", "Sleep Score", "Sleep Length", "HRV (ms)", "HRV Status", "Weight (kg)", "Body Fat %",
    "Blood Pressure Systolic", "Blood Pressure Diastolic", "Active Calories",
    "Resting Calories", "Resting Heart Rate", "Average Stress", "Training Status",
    "VO2 Max Running", "VO2 Max Cycling", "Intensity Minutes", "All Activity Count",
    "Running Activity Count", "Running Distance (km)", "Cycling Activity Count",
    "Cycling Distance (km)", "Strength Activity Count", "Strength Duration",
    "Cardio Activity Count", "Cardio Duration" # HRV (ms) moved to after Sleep Length
]

# Mapping from CSV Header to potential GarminMetrics attribute name (adjust if needed)
# Assuming snake_case for attributes based on Python conventions
HEADER_TO_ATTRIBUTE_MAP = {
    "Date": "date",
    "Sleep Score": "sleep_score",
    "Sleep Length": "sleep_length", # Or sleep_duration? Assuming sleep_length
    "Weight (kg)": "weight_kg",
    "Body Fat %": "body_fat_percentage",
    "Blood Pressure Systolic": "bp_systolic",
    "Blood Pressure Diastolic": "bp_diastolic",
    "Active Calories": "active_calories",
    "Resting Calories": "resting_calories",
    "Resting Heart Rate": "resting_heart_rate",
    "Average Stress": "average_stress",
    "Training Status": "training_status",
    "VO2 Max Running": "vo2_max_running",
    "VO2 Max Cycling": "vo2_max_cycling",
    "Intensity Minutes": "intensity_minutes",
    "All Activity Count": "all_activity_count",
    "Running Activity Count": "running_activity_count",
    "Running Distance (km)": "running_distance_km",
    "Cycling Activity Count": "cycling_activity_count",
    "Cycling Distance (km)": "cycling_distance_km",
    "Strength Activity Count": "strength_activity_count",
    "Strength Duration": "strength_duration",
    "Cardio Activity Count": "cardio_activity_count",
    "Cardio Duration": "cardio_duration",
    "HRV (ms)": "overnight_hrv", # Added HRV mapping
    "HRV Status": "hrv_status"
}


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

# --- Interactive Mode Function ---

async def run_interactive_sync():
    """Handles the interactive session to gather parameters and run the sync."""
    logger.info("Starting interactive sync setup...")

    # --- Output Type Selection ---
    output_type = ""
    while output_type not in ["csv", "sheets"]:
        print("\nData output select:")
        print("1 for local CSV")
        print("2 for Google Sheets")
        choice = input("Enter choice (1 or 2): ").strip()
        if choice == '1':
            output_type = "csv"
        elif choice == '2':
            output_type = "sheets"
        else:
            print("Invalid choice. Please enter 1 or 2.")

    logger.info(f"Selected output type: {output_type}")

    output_target = None # Will store CSV path or Sheet ID

    # --- Load Profiles ---
    # Load environment variables (needed for profiles)
    load_dotenv()
    user_profiles = load_user_profiles()
    if not user_profiles:
        logger.error("No user profiles found in .env file. Please define at least one profile (e.g., USER1_GARMIN_EMAIL=...).")
        sys.exit(1)
    logger.info(f"Loaded {len(user_profiles)} user profiles: {list(user_profiles.keys())}")


    # --- Profile Selection ---
    profile_names = list(user_profiles.keys())
    print("\nAvailable User Profiles:")
    for i, name in enumerate(profile_names):
        # Display email instead of profile name
        email_display = user_profiles[name].get('email', 'Email not found') # Safely get email
        print(f"{i + 1}. {email_display}")

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
    sheets_id = selected_profile_data.get('sheet_id') # Get sheet_id, needed if output is sheets
    logger.info(f"Using profile: {selected_profile_name}")

    # --- Set Output Target based on type and profile ---
    if output_type == 'sheets':
        if not sheets_id:
            logger.error(f"Sheet ID is missing for profile '{selected_profile_name}' but output type is 'sheets'. Cannot proceed.")
            sys.exit(1)
        output_target = sheets_id
        logger.info(f"Target Google Sheet ID: {output_target}")
    elif output_type == 'csv':
        # Define fixed output directory and construct filename
        output_dir = Path("./output")
        filename = f"garmingo_{selected_profile_name}.csv"
        output_target = output_dir / filename # output_target is now a Path object
        logger.info(f"Target CSV file path set to: {output_target}")
        # No user input needed for CSV path anymore


    # --- Date Input ---
    date_format = "%Y-%m-%d"
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    while True:
        try:
            start_date_str = input("Enter start date (YYYY-MM-DD): ")
            start_date = datetime.strptime(start_date_str, date_format).date() # Store as date object
            break
        except ValueError:
            print(f"Invalid date format. Please use {date_format}.")

    while True:
        try:
            end_date_str = input("Enter end date (YYYY-MM-DD): ")
            end_date = datetime.strptime(end_date_str, date_format).date() # Store as date object
            if end_date >= start_date:
                break
            else:
                print("End date cannot be before start date.")
        except ValueError:
            print(f"Invalid date format. Please use {date_format}.")

    logger.info(f"Date range selected: {start_date.strftime(date_format)} to {end_date.strftime(date_format)}")

    # --- Call Core Sync Logic ---
    await sync(
        email=email,
        password=password,
        start_date=start_date,
        end_date=end_date,
        output_type=output_type,
        output_target=output_target # Pass CSV path or Sheet ID
    )


# --- Core Sync Logic (Modified) ---

async def sync(email: str, password: str, start_date: date, end_date: date, output_type: str, output_target: Path | str):
    """
    Core sync logic. Fetches data from Garmin and writes to the specified output.
    Accepts all necessary parameters directly.
    output_target: Path object for CSV, string (Sheet ID) for Sheets.
    """
    try:
        # Parameters are now passed directly
        date_format = "%Y-%m-%d" # Keep for logging/formatting

        # Initialize Garmin client using passed credentials
        logger.info("Initializing Garmin client...")
        garmin_client = GarminClient(email, password)

        logger.info(f"Starting sync from {start_date.strftime(date_format)} to {end_date.strftime(date_format)} for user {email}")

        # Authenticate with Garmin using passed credentials
        logger.info("Authenticating with Garmin...")
        try:
            await garmin_client.authenticate()
        except GarthHTTPError as auth_err:
            # Check if the error is likely an authentication failure (e.g., 401)
            # Note: Garth might not expose status code directly, checking string is a common fallback
            if "401" in str(auth_err) or "Unauthorized" in str(auth_err):
                 logger.error(f"Garmin authentication failed for {email}: {auth_err}")
                 print(f"\nGarmin authentication failed for {email}.")
                 print("Please check the username and password for the selected profile in your configuration (e.g., .env file).")
                 # Exit gracefully for this specific error
                 # Depending on context, you might 'return' instead of 'sys.exit' if called elsewhere
                 sys.exit(1)
            else:
                # Re-raise other GarthHTTPErrors to be caught by the general handler
                logger.error(f"An unexpected Garmin HTTP error occurred: {auth_err}", exc_info=True)
                raise # Re-raise the original error

        # Get metrics for each day in the date range
        logger.info("Fetching metrics from Garmin...")
        metrics = []
        current_date = start_date # Use passed start_date
        while current_date <= end_date: # Use passed end_date
            logger.info(f"Fetching metrics for {current_date}")
            daily_metrics = await garmin_client.get_metrics(current_date)
            if daily_metrics: # Ensure daily_metrics is not None before accessing attributes
                pass
            metrics.append(daily_metrics)
            current_date += timedelta(days=1)

        if not metrics:
             logger.warning("No metrics fetched from Garmin. Nothing to write.")
             print("\nNo metrics data found for the selected date range.")
             # Decide if we should exit or just finish gracefully
             # sys.exit(0) # Or just let it finish
             return # Exit the sync function if no data

        # --- Output based on selected type ---
        if output_type == 'sheets':
            # output_target should be the Sheet ID (string)
            if not isinstance(output_target, str):
                 logger.error(f"Internal error: Expected Sheet ID (string) for output_target, but got {type(output_target)}")
                 sys.exit(1)
            sheets_id = output_target
            # Initialize Google Sheets client and update sheet
            try:
                logger.info("Initializing Google Sheets client...")
                sheets_client = GoogleSheetsClient(
                    credentials_path='credentials/client_secret.json',
                    spreadsheet_id=sheets_id
                )

                logger.info("Updating Google Sheet...")
                sheets_client.update_metrics(metrics)

                logger.info("Google Sheets sync completed successfully!")

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
            except Exception as sheet_error: # Catch other potential sheets errors
                 logger.error(f"An error occurred during Google Sheets operation: {str(sheet_error)}", exc_info=True)
                 print(f"\nAn error occurred while updating Google Sheets: {sheet_error}")
                 sys.exit(1)

        elif output_type == 'csv':
            # output_target should be the Path object
            if not isinstance(output_target, Path):
                 logger.error(f"Internal error: Expected Path object for output_target, but got {type(output_target)}")
                 sys.exit(1)
            csv_file_path = output_target

            try:
                # Check if file exists to determine if headers are needed
                file_exists = csv_file_path.exists()
                # Ensure parent directory exists
                csv_file_path.parent.mkdir(parents=True, exist_ok=True)

                logger.info(f"Writing metrics to CSV file: {csv_file_path} (Append: {file_exists})")
                # Use 'a' for append, 'w' for write (which happens if file_exists is False)
                # newline='' is crucial for csv writer on Windows
                with open(csv_file_path, mode='a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
                    # Use the predefined CSV_HEADERS for the writer
                    writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)

                    if not file_exists:
                        writer.writeheader() # Write header only if file is new

                    # Iterate through metrics objects and write rows, mapping attributes
                    for metric_object in metrics:
                        row_dict = {}
                        for header in CSV_HEADERS:
                            value = None # Default value
                            try:
                                # --- Specific Handling for Problematic Fields ---
                                if header == "Weight (kg)":
                                    # Assume 'weight' attribute exists and is in grams
                                    raw_weight = getattr(metric_object, 'weight', None)
                                    if raw_weight is not None:
                                        value = raw_weight / 1000.0 # Convert grams to kg
                                elif header == "Body Fat %":
                                    # Try 'body_fat' first, then 'body_fat_percentage'
                                    value = getattr(metric_object, 'body_fat', None)
                                    if value is None:
                                        value = getattr(metric_object, 'body_fat_percentage', None)
                                elif header == "VO2 Max Running":
                                    # Specific handling using the correct attribute name
                                    value = getattr(metric_object, 'vo2max_running', None)
                                elif header == "VO2 Max Cycling":
                                    # Specific handling using the correct attribute name
                                    value = getattr(metric_object, 'vo2max_cycling', None)
                                elif header == "Running Distance (km)":
                                    # Assume 'running_distance' attribute exists and is already in km
                                    raw_distance = getattr(metric_object, 'running_distance', None)
                                    if raw_distance is not None:
                                        value = raw_distance # Assign directly, assuming km
                                elif header == "Cycling Distance (km)":
                                    # Assume 'cycling_distance' attribute exists and is already in km
                                    raw_distance = getattr(metric_object, 'cycling_distance', None)
                                    if raw_distance is not None:
                                        value = raw_distance # Assign directly, assuming km
                                else:
                                    # --- Default Handling for Other Headers ---
                                    attribute_name = HEADER_TO_ATTRIBUTE_MAP.get(header)
                                    if attribute_name:
                                        value = getattr(metric_object, attribute_name, None)
                                    else:
                                        logger.warning(f"No attribute mapping found for header: {header}")
                                        value = None

                            except AttributeError:
                                # Log if an expected attribute is missing (less verbose)
                                logger.warning(f"Attribute not found for header '{header}' on metric object for date {getattr(metric_object, 'date', 'Unknown')}", exc_info=False)
                                value = None # Ensure value is None
                            except TypeError:
                                # Log if a conversion fails (e.g., None / 1000)
                                logger.warning(f"Type error during processing for header '{header}' on metric object for date {getattr(metric_object, 'date', 'Unknown')}", exc_info=False)
                                value = None # Ensure value is None on type error

                            # --- Value Formatting ---
                            formatted_value = "" # Default formatted value
                            if header in ["Date", "Training Status", "HRV Status"]:
                                # Ensure non-None values are strings for these specific fields
                                # HRV Status is a string (e.g., "BALANCED") and should not be converted to float.
                                formatted_value = str(value) if value is not None else ""
                            else:
                                # Attempt numeric conversion and rounding for other fields
                                try:
                                    # Only attempt conversion if value is not None and not an empty string
                                    if value is not None and value != '':
                                        float_value = float(value)
                                        rounded_value = round(float_value, 2)
                                        formatted_value = str(rounded_value)
                                    # If value was None or empty string initially, formatted_value remains ""
                                except (ValueError, TypeError): # Catch potential errors during float conversion
                                    # If conversion fails, keep it as an empty string
                                    logger.debug(f"Could not convert value '{value}' for header '{header}' to float. Setting to empty string.")
                                    formatted_value = "" # Keep as empty string on error

                            row_dict[header] = formatted_value # Assign the formatted string value

                        writer.writerow(row_dict)

                logger.info(f"Successfully wrote {len(metrics)} rows to {csv_file_path}")
                print(f"\nSuccessfully saved data to {csv_file_path}")

                # --- Open Output Directory ---
                output_dir_str = str(csv_file_path.parent.resolve()) # Get absolute path as string
                logger.info(f"Attempting to open output directory: {output_dir_str}")
                try:
                    if sys.platform == 'win32':
                        os.startfile(output_dir_str)
                        logger.info("Opened directory using os.startfile (Windows).")
                    elif sys.platform == 'darwin':
                        subprocess.run(['open', output_dir_str], check=True)
                        logger.info("Opened directory using subprocess.run 'open' (macOS).")
                    elif sys.platform.startswith('linux'):
                        subprocess.run(['xdg-open', output_dir_str], check=True)
                        logger.info("Opened directory using subprocess.run 'xdg-open' (Linux).")
                    else:
                        logger.warning(f"Unsupported platform '{sys.platform}'. Cannot automatically open directory.")
                        print(f"\nCSV saved. Please manually open the output directory: {output_dir_str}")
                except FileNotFoundError:
                     logger.error(f"Error opening directory: Command not found (e.g., 'open' or 'xdg-open'). Is the necessary utility installed?")
                     print(f"\nCSV saved. Could not automatically open the output directory: {output_dir_str}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error opening directory using subprocess: {e}")
                    print(f"\nCSV saved. Could not automatically open the output directory: {output_dir_str}")
                except Exception as e: # Catch other potential errors like permission issues
                    logger.error(f"An unexpected error occurred while trying to open the directory: {e}", exc_info=True)
                    print(f"\nCSV saved. Could not automatically open the output directory: {output_dir_str}")
                # --- End Open Output Directory ---

            except (IOError, OSError, csv.Error) as csv_error:
                logger.error(f"Error writing to CSV file {csv_file_path}: {csv_error}", exc_info=True)
                print(f"\nError writing to CSV file '{csv_file_path}': {csv_error}")
                sys.exit(1)
        else:
             # This case should ideally not be reached due to earlier checks
             logger.error(f"Invalid output_type '{output_type}' reached core sync logic.")
             sys.exit(1)

        logger.info("Sync process finished.")
    # This is the general exception handler for the outer try block
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


# --- Typer App (for potential future CLI use, not default) ---
@app.command(name="cli-sync") # Rename command to avoid conflict if needed
def sync_wrapper(
    output_type: str = typer.Option(
        ..., # Make required if using CLI directly
        "--output-type",
        "-o",
        help="Output format ('sheets' or 'csv').",
        case_sensitive=False,
    ),
    profile_name: str = typer.Option(
        ..., # Make required
        "--profile",
        "-p",
        help="Name of the user profile from .env (e.g., USER1)."
    ),
    start_date_str: str = typer.Option(
        ..., # Make required
        "--start-date",
        help="Start date in YYYY-MM-DD format."
    ),
    end_date_str: str = typer.Option(
        ..., # Make required
        "--end-date",
        help="End date in YYYY-MM-DD format."
    ),
    csv_path: Optional[str] = typer.Option( # Optional, only needed for CSV
        None,
        "--csv-path",
        help="Output CSV file path (required if output-type is 'csv')."
    )
):
    """
    (CLI Interface - Not default) Sync Garmin Connect data. Requires all parameters via flags.
    """
    output_type = output_type.lower()
    if output_type not in ["sheets", "csv"]:
        logger.error("Invalid output type. Use 'sheets' or 'csv'.")
        sys.exit(1)
    if output_type == 'csv' and not csv_path:
        logger.error("--csv-path is required when --output-type is 'csv'.")
        sys.exit(1)

    # Load .env and profiles
    load_dotenv()
    user_profiles = load_user_profiles()
    if profile_name not in user_profiles:
        logger.error(f"Profile '{profile_name}' not found in .env file or is incomplete.")
        sys.exit(1)

    profile_data = user_profiles[profile_name]
    email = profile_data['email']
    password = profile_data['password']
    sheets_id = profile_data.get('sheet_id')

    if output_type == 'sheets' and not sheets_id:
        logger.error(f"Sheet ID is missing for profile '{profile_name}' but output type is 'sheets'.")
        sys.exit(1)

    # Validate dates
    date_format = "%Y-%m-%d"
    try:
        start_date = datetime.strptime(start_date_str, date_format).date()
        end_date = datetime.strptime(end_date_str, date_format).date()
        if end_date < start_date:
            logger.error("End date cannot be before start date.")
            sys.exit(1)
    except ValueError:
        logger.error(f"Invalid date format. Please use {date_format}.")
        sys.exit(1)

    # Determine output target
    output_target: Path | str
    if output_type == 'csv':
        output_target = Path(csv_path) # csv_path is guaranteed non-None here
    else: # sheets
        output_target = sheets_id # sheets_id is guaranteed non-None here

    # Run the core sync logic
    asyncio.run(sync(
        email=email,
        password=password,
        start_date=start_date,
        end_date=end_date,
        output_type=output_type,
        output_target=output_target
    ))
    logger.info("CLI Sync command finished.")


# --- Main Execution ---
if __name__ == "__main__":
    # Default behavior: run the interactive mode
    # ASCII Art for GarminGo (Removed)
    # ascii_art = r"""...""" # Removed multi-line ASCII art

    # --- Boxed Welcome Message ---
    welcome_lines = [
        "Welcome to GarminGo!",
        "Let's help you make data-driven health and longevity decisions by grabbing your Garmin data."
    ]
    # Find the longest line to determine box width
    max_len = 0
    for line in welcome_lines:
        if len(line) > max_len:
            max_len = len(line)

    # Define padding and calculate widths
    internal_padding_each_side = 2
    internal_width = max_len + (internal_padding_each_side * 2) # Width inside the side borders
    # Total width includes the side borders '* ' and ' *'
    total_width = 1 + 1 + internal_width + 1 + 1 # '* ' + internal + ' *'
    border_len = total_width # Width includes the side borders '* ' and ' *'

    # Construct border and blank padded line
    border = "*" * border_len
    blank_padded_line = f"* {' ' * internal_width} *"

    # Print the welcome screen with new formatting
    print() # Add blank line BEFORE the box
    print(border)
    print(blank_padded_line)
    for line in welcome_lines:
        # Calculate padding for the internal width
        padding_total = internal_width - len(line)
        padding_left = padding_total // 2
        padding_right = padding_total - padding_left
        print(f"* {' ' * padding_left}{line}{' ' * padding_right} *")
    print(blank_padded_line)
    print(border)
    # --- End Boxed Welcome Message ---
    # The print() below adds space AFTER the box, keep it.
    print()

    try:
        asyncio.run(run_interactive_sync())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    # To run the CLI version (e.g., for automation):
    # python -m src.main cli-sync --output-type csv --profile USER1 --start-date 2023-01-01 --end-date 2023-01-02 --csv-path output.csv
    # Or use typer's entry point mechanism if properly configured in pyproject.toml etc.
    # app() # Keep this line commented out or remove if CLI is never intended via direct `python -m src.main` call