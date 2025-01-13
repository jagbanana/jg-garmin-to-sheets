from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials/client_secret.json', SCOPES)
creds = flow.run_local_server(port=0)

with open('credentials/token.pickle', 'wb') as token:
    pickle.dump(creds, token)