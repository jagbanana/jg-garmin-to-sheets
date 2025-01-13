from typing import List
import os.path
import os
from google.oauth2.credentials import Credentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import date
import pickle
from pathlib import Path

from .garmin_client import GarminMetrics

# If modifying these scopes, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class GoogleSheetsClient:
    def __init__(self, credentials_path: str, spreadsheet_id: str):
    self.spreadsheet_id = spreadsheet_id
    
    # Add environment variable handling here
    credentials_dir = os.getenv('GOOGLE_CREDENTIALS_DIR', 'credentials')
    client_secret_file = os.getenv('GOOGLE_CLIENT_SECRET_FILE', 'client_secret.json')
    token_file = os.getenv('GOOGLE_TOKEN_FILE', 'token.pickle')

    credentials_path = Path(credentials_dir) / client_secret_file
    token_path = Path(credentials_dir) / token_file
    
    self.credentials_path = str(credentials_path)  # Convert Path to string
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
                creds.refresh(Request())
            else:
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
            'Date', 'Sleep Score', 'Sleep Length', 'Weight', 'Body Fat %', 
            'Blood Pressure Systolic', 'Blood Pressure Diastolic', 
            'Active Calories', 'Resting Calories', 'Resting Heart Rate',
            'Average Stress', 'Training Status', 
            'VO2 Max Running', 'VO2 Max Cycling',
            'Intensity Minutes', 'All Activity Count', 
            'Running Activity Count', 'Running Distance',
            'Cycling Activity Count', 'Cycling Distance',
            'Strength Activity Count', 'Strength Duration',
            'Cardio Activity Count', 'Cardio Duration'
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
                metric.cardio_duration
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
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()