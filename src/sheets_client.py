import logging
from typing import List
from pathlib import Path
import pickle
from datetime import date # Import the date type
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.auth.exceptions
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import GarminMetrics, HEADERS, HEADER_TO_ATTRIBUTE_MAP

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class GoogleAuthTokenRefreshError(Exception):
    """Raised when the Google API token refresh fails."""
    pass

class GoogleSheetsClient:
    def __init__(self, credentials_path: str, spreadsheet_id: str, sheet_name: str):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.credentials_path = credentials_path
        self.credentials = self._get_credentials()
        self.service = build('sheets', 'v4', credentials=self.credentials)
        self.spreadsheet_title = None # To store the human-readable name

    def _get_credentials(self) -> Credentials:
        creds = None
        token_path = Path(self.credentials_path).parent / 'token.pickle'
        
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
                
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except google.auth.exceptions.RefreshError as e:
                    raise GoogleAuthTokenRefreshError(f"Google token refresh failed: {e}")
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        return creds

    def _get_spreadsheet_details(self):
        """Fetches spreadsheet metadata to get sheet properties and title."""
        try:
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            self.spreadsheet_title = sheet_metadata['properties']['title']
            return sheet_metadata.get('sheets', [])
        except HttpError as e:
            logger.error(f"An error occurred fetching spreadsheet details: {e}")
            raise

    def _setup_sheet(self, all_sheets_properties):
        """Ensures the sheet exists and has headers."""
        sheet_exists = any(s['properties']['title'] == self.sheet_name for s in all_sheets_properties)
        
        if not sheet_exists:
            logger.info(f"Sheet '{self.sheet_name}' not found in '{self.spreadsheet_title}'. Creating it now.")
            body = {'requests': [{'addSheet': {'properties': {'title': self.sheet_name}}}]}
            self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()

        range_to_check = f"'{self.sheet_name}'!A1"
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=range_to_check
        ).execute()

        if 'values' not in result:
            logger.info(f"Sheet '{self.sheet_name}' is empty. Writing headers.")
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_to_check,
                valueInputOption='RAW',
                body={'values': [HEADERS]}
            ).execute()

    def update_metrics(self, metrics: List[GarminMetrics]):
        """Updates or appends metrics to the Google Sheet."""
        all_sheets_properties = self._get_spreadsheet_details()
        self._setup_sheet(all_sheets_properties)
        
        try:
            date_column_range = f"'{self.sheet_name}'!A:A"
            result = self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=date_column_range).execute()
            existing_dates_list = result.get('values', [])
            date_to_row_map = {row[0]: i + 1 for i, row in enumerate(existing_dates_list) if row}
        except HttpError as e:
            logger.error(f"Could not read existing dates from sheet: {e}")
            return

        updates = []
        appends = []

        for metric in metrics:
            # Convert the date object to an ISO format string for JSON serialization
            metric_date_str = metric.date.isoformat() if isinstance(metric.date, date) else metric.date
            
            row_data = []
            for header in HEADERS:
                attribute_name = HEADER_TO_ATTRIBUTE_MAP.get(header)
                value = getattr(metric, attribute_name, "") if attribute_name else ""
                
                # Special handling for the date to ensure it's a string
                if attribute_name == 'date':
                    value = metric_date_str

                if value is None:
                    value = ""
                elif isinstance(value, float):
                    value = round(value, 2)
                
                row_data.append(value)

            if metric_date_str in date_to_row_map:
                row_number = date_to_row_map[metric_date_str]
                updates.append({
                    'range': f"'{self.sheet_name}'!A{row_number}",
                    'values': [row_data]
                })
            else:
                appends.append(row_data)

        if updates:
            logger.info(f"Updating {len(updates)} existing rows in '{self.spreadsheet_title}'.")
            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': updates
            }
            self.service.spreadsheets().values().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()

        if appends:
            logger.info(f"Appending {len(appends)} new rows to '{self.spreadsheet_title}'.")
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{self.sheet_name}'!A1",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': appends}
            ).execute()

        if not updates and not appends:
            logger.info("No new data to update or append.")
