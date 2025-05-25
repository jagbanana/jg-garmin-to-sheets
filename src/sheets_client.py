from typing import List
import os.path
from google.oauth2.credentials import Credentials
from google.oauth2.credentials import Credentials # Duplicate removed by keeping one
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.auth.exceptions # Added import
from googleapiclient.discovery import build
from datetime import date
import pickle
from pathlib import Path

from .garmin_client import GarminMetrics

# If modifying these scopes, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Custom exception for token refresh failures
class GoogleAuthTokenRefreshError(Exception):
    """Raised when the Google API token refresh fails."""
    pass

class GoogleSheetsClient:
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.credentials = self._get_credentials()
        self.service = build('sheets', 'v4', credentials=self.credentials)

    def _get_credentials(self) -> Credentials:
        """Gets valid user credentials from storage or initiates OAuth2 flow."""
        creds = None
        token_path = Path(self.credentials_path).parent / 'token.pickle'
        
        # The file token.pickle stores the user's access and refresh tokens
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
                
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except google.auth.exceptions.RefreshError as e:
                    # Raise custom exception if refresh fails
                    raise GoogleAuthTokenRefreshError(f"Google token refresh failed: {e}")
            else:
                # This part remains the same, handling initial auth or non-refreshable tokens
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def _setup_sheet(self):
        """Sets up the sheet with headers if it doesn't exist."""
        headers = [
            'Date', 'Sleep Score', 'Sleep Length', 'HRV (ms)', 'HRV Status', 'Weight', 'Body Fat %',
            'Blood Pressure Systolic', 'Blood Pressure Diastolic',
            'Active Calories', 'Resting Calories', 'Resting Heart Rate',
            'Average Stress', 'Training Status',
            'VO2 Max Running', 'VO2 Max Cycling',
            'Intensity Minutes', 'All Activity Count',
            'Running Activity Count', 'Running Distance',
            'Cycling Activity Count', 'Cycling Distance',
            'Strength Activity Count', 'Strength Duration',
            'Cardio Activity Count', 'Cardio Duration',
            'Tennis Activity Count', 'Tennis Activity Duration' # Added Tennis
        ]
        
        # Check if sheet is empty
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range='A1:Z1'
        ).execute()
        
        if 'values' not in result:  # Sheet is empty
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='A1',
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()

    def update_metrics(self, metrics: List[GarminMetrics]):
        """Updates the Google Sheet with the provided metrics."""
        self._setup_sheet()
        
        # Convert metrics to rows
        rows = []
        for metric in metrics:
            row = [
                metric.date.strftime('%Y-%m-%d'),
                metric.sleep_score,
                metric.sleep_length,
                metric.overnight_hrv,
                metric.hrv_status, # Added HRV Status data
                metric.weight,
                metric.body_fat,
                metric.blood_pressure_systolic,
                metric.blood_pressure_diastolic,
                metric.active_calories,
                metric.resting_calories,
                metric.resting_heart_rate,
                metric.average_stress,
                metric.training_status,
                metric.vo2max_running,
                metric.vo2max_cycling,
                metric.intensity_minutes,
                metric.all_activity_count,
                metric.running_activity_count,
                metric.running_distance,
                metric.cycling_activity_count,
                metric.cycling_distance,
                metric.strength_activity_count,
                metric.strength_duration,
                metric.cardio_activity_count,
                metric.cardio_duration,
                metric.tennis_activity_count, # Added Tennis
                metric.tennis_activity_duration # Added Tennis
            ]
            rows.append(row)
        
        # Find the first empty row
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range='A:A'
        ).execute()
        next_row = len(result.get('values', [])) + 1
        
        # Update the sheet
        range_name = f'A{next_row}'
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body={'values': rows}
        ).execute()