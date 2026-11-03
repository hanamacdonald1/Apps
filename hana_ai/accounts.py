"""OAuth credentials live in the OS credential vault, never in the repository."""
import base64
import json
import re
from email.message import EmailMessage

import keyring
import msal
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from hana_ai.store import setting, save_setting

GMAIL_READ = ['https://www.googleapis.com/auth/gmail.readonly']
GMAIL_SEND = 'https://www.googleapis.com/auth/gmail.send'
GRAPH = 'https://graph.microsoft.com/v1.0'
VAULT = 'HanaAI'


def secret(name):
    return keyring.get_password(VAULT, name)


def save_secret(name, value):
    keyring.set_password(VAULT, name, value)


def disconnect(provider):
    for name in ([ 'gmail_token' ] if provider == 'gmail' else ['outlook_cache']):
        if secret(name):
            keyring.delete_password(VAULT, name)
    save_setting(provider + '_connected', False)


def connect_gmail(config_text, allow_send=False):
    scopes = GMAIL_READ + ([GMAIL_SEND] if allow_send else [])
    flow = InstalledAppFlow.from_client_config(json.loads(config_text), scopes)
    creds = flow.run_local_server(host='127.0.0.1', port=0, timeout_seconds=180)
    save_secret('gmail_token', creds.to_json())
    save_setting('gmail_connected', True)


def gmail():
    raw = secret('gmail_token')
    if not raw:
        raise RuntimeError('Connect Gmail first.')
    creds = Credentials.from_authorized_user_info(json.loads(raw))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_secret('gmail_token', creds.to_json())
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def microsoft():
    client_id = setting('microsoft_client_id', '')
    if not client_id:
        raise RuntimeError('Add your Microsoft application client ID first.')
    cache = msal.SerializableTokenCache()
    saved = secret('outlook_cache')
    if saved:
        cache.deserialize(saved)
    app = msal.PublicClientApplication(client_id, authority='https://login.microsoftonline.com/common', token_cache=cache)
    return app, cache


def begin_outlook(allow_send=False):
    app, _ = microsoft()
    scopes = ['Mail.Read'] + (['Mail.Send'] if allow_send else [])
    flow = app.initiate_device_flow(scopes=scopes)
    if 'user_code' not in flow:
        raise RuntimeError('Microsoft sign-in could not start. Check app registration and public client setting.')
    return flow, scopes


def finish_outlook(flow, scopes):
    app, cache = microsoft()
    result = app.acquire_token_by_device_flow(flow)
    if 'access_token' not in result:
        raise RuntimeError('Microsoft sign-in failed or expired. Start sign-in again.')
    save_secret('outlook_cache', cache.serialize())
    save_setting('outlook_scopes', scopes)
    save_setting('outlook_connected', True)


def outlook_token():
    app, cache = microsoft()
    accounts = app.get_accounts()
    result = app.acquire_token_silent(setting('outlook_scopes', ['Mail.Read']), account=accounts[0]) if accounts else None
    if cache.has_state_changed:
        save_secret('outlook_cache', cache.serialize())
    if not result or 'access_token' not in result:
        raise RuntimeError('Reconnect Outlook to renew account access.')
    return result['access_token']


def read_mail(provider, limit=50):
    """Bounded metadata scan. Full bodies are not downloaded or rendered."""
    if provider == 'gmail':
        service = gmail()
        result = service.users().messages().list(userId='me', q='newer_than:30d', maxResults=limit).execute()
        rows = []
        for entry in result.get('messages', []):
            msg = service.users().messages().get(userId='me', id=entry['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']).execute()
            headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
            rows.append({'id': msg['id'], 'provider': provider, 'sender': headers.get('from', ''),
                         'subject': headers.get('subject', ''), 'date': headers.get('date', ''),
                         'preview': msg.get('snippet', ''), 'url': 'https://mail.google.com/mail/u/0/#all/' + msg['id']})
        return rows
    token = outlook_token()
    response = requests.get(GRAPH + '/me/messages', headers={'Authorization': 'Bearer ' + token},
        params={'$top': limit, '$select': 'id,subject,from,receivedDateTime,bodyPreview,webLink',
                '$orderby': 'receivedDateTime desc'}, timeout=30)
    response.raise_for_status()
    return [{'id': m['id'], 'provider': provider, 'sender': m.get('from', {}).get('emailAddress', {}).get('address', ''),
             'subject': m.get('subject', ''), 'date': m.get('receivedDateTime', ''),
             'preview': m.get('bodyPreview', '')[:1200], 'url': m.get('webLink', '')}
            for m in response.json().get('value', [])]


def send_mail(provider, recipient, subject, body):
    if not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+', recipient):
        raise ValueError('Enter one valid recipient email address.')
    if '\n' in subject or '\r' in subject:
        raise ValueError('Subject cannot contain a newline.')
    if provider == 'gmail':
        message = EmailMessage()
        message['To'], message['Subject'] = recipient, subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        gmail().users().messages().send(userId='me', body={'raw': raw}).execute()
    elif provider == 'outlook':
        response = requests.post(GRAPH + '/me/sendMail',
            headers={'Authorization': 'Bearer ' + outlook_token()},
            json={'message': {'subject': subject, 'body': {'contentType': 'Text', 'content': body},
                  'toRecipients': [{'emailAddress': {'address': recipient}}]}, 'saveToSentItems': True}, timeout=30)
        response.raise_for_status()
    else:
        raise ValueError('Unknown provider')
