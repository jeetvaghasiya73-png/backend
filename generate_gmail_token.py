import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(backend_dir, 'token.json')
    creds_path = os.path.join(backend_dir, 'credentials.json')

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                print(f"ERROR: credentials.json not found at {creds_path}!")
                return
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            try:
                creds = flow.run_local_server(host='localhost', port=8080, open_browser=True)
            except Exception:
                creds = flow.run_local_server(port=0, open_browser=True)

            
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            print(f"✓ Successfully generated {token_path}!")
            print("Notice: token.json and credentials.json are ignored by git for security.")

if __name__ == '__main__':
    main()

