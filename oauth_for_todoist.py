import urllib.parse
import secrets
from dotenv import load_dotenv
import os 

CLIENT_ID = os.getenv("CLIENT_ID")
SCOPES = ["data:read_write", "task:add"] 
STATE = secrets.token_urlsafe(16) 

params = {
    "client_id": CLIENT_ID,
    "scope": ",".join(SCOPES),
    "state": STATE
}

auth_url = f"https://api.todoist.com/oauth/authorize?{urllib.parse.urlencode(params)}"

print(auth_url)
