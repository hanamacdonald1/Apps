"""Hana AI: local agent dashboard. Start with streamlit run app.py."""
import json
import time
from urllib.parse import urlsplit

import requests
import streamlit as st

from hana_ai import accounts, agents, store

st.set_page_config(page_title='Hana AI', page_icon='✨', layout='wide')
st.title('✨ Hana AI')
st.caption('Your personal agents · jobs · inbox · subscriptions')

@st.cache_data(ttl=15)
def models():
    try:
        r = requests.get('http://127.0.0.1:11434/api/tags', timeout=2)
        r.raise_for_status()
        return [m['name'] for m in r.json().get('models', [])]
    except (requests.RequestException, ValueError, KeyError):
        return []


def safe_link(label, url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and not parsed.password:
            st.link_button(label, url)
    except ValueError:
        pass


def run_scan(function):
    with st.spinner('Agent working…'):
        try:
            result = function()
            st.json(result)
        except Exception:
            st.error('Scan failed. Check connections and settings. No sensitive error details were logged.')


def toggle_agents():
    store.save_setting('paused', not st.session_state['agents_enabled'])


def pause_agents():
    store.save_setting('paused', True)
    st.session_state['agents_enabled'] = False


with st.sidebar:
    st.header('Agent control')
    if 'agents_enabled' not in st.session_state:
        st.session_state['agents_enabled'] = not store.setting('paused', True)
    st.toggle('Enable agent actions', key='agents_enabled', on_change=toggle_agents)
    st.caption('Pause stops new scheduled tasks and queued sends. A request already in progress may finish.')
    st.button('⏸ Pause all agents', type='primary', on_click=pause_agents)
    installed = models()
    model = st.selectbox('Local AI model', installed) if installed else None
    if not model:
        st.info('Install Ollama, then run: ollama pull qwen3:4b')
    heartbeat = store.setting('heartbeat', 0)
    running = heartbeat and time.time() - heartbeat < 120
    st.metric('Background worker', 'Online' if running else 'Not detected')
    st.caption('Run python worker.py for scheduled work. Your computer must stay awake.')
    st.caption('Mail tokens and API keys use the OS credential vault. Jobs, email previews and notes are stored locally.')

chat, jobs, inbox, subscriptions, actions, settings, activity = st.tabs(
    ['💬 Assistant', '🔎 Jobs', '📨 Inbox', '💳 Subscriptions', '✅ Actions', '⚙ Settings', '📋 Activity'])

with chat:
    st.subheader('Ask your agents')
    st.caption('Try: “Scan for jobs and show my strongest matches” or “Review my inbox for subscriptions”. Tool-capable Ollama model required.')
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if st.button('Clear conversation'):
        st.session_state.messages = []
        st.rerun()
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    prompt = st.chat_input('What should your assistant work on?', disabled=not model)
    if prompt:
        st.session_state.messages.append({'role': 'user', 'content': prompt})
        with st.chat_message('user'):
            st.markdown(prompt)
        with st.chat_message('assistant'):
            try:
                with st.spinner('Coordinating agents…'):
                    answer, trace = agents.agent_chat(model, st.session_state.messages, store.setting('background', ''))
                st.markdown(answer)
                if trace:
                    st.caption('Tools used: ' + ', '.join(trace))
                st.session_state.messages.append({'role': 'assistant', 'content': answer})
            except Exception:
                st.error('Local model could not complete the request. Check Ollama and use a model supporting tool calls. The dashboard buttons also work without AI.')
                st.session_state.messages.pop()

with jobs:
    st.subheader('Job scout')
    st.caption('Live Adzuna Australia search and your configured RSS/Atom feeds. Add sources in Settings. Keyword coverage is transparent; it is not a hiring probability.')
    if st.button('Scan jobs now'):
        run_scan(agents.scan_jobs)
    records = sorted(store.items('job'), key=lambda j: j.get('score', 0), reverse=True)
    c1, c2 = st.columns(2)
    filter_stage = c1.selectbox('Show stage', ['All', 'New', 'Shortlisted', 'Applied', 'Archived'])
    min_score = c2.slider('Minimum keyword coverage', 0, 100, 0)
    for job in records:
        if job.get('score', 0) < min_score or filter_stage not in ('All', job.get('stage', 'New')):
            continue
        with st.expander(f"{job.get('score', 0)}% · {job['title']} · {job.get('company', '')}"):
            st.write(job.get('location', ''), job.get('posted', ''))
            st.write(job.get('description', ''))
            st.caption('Matched terms: ' + ', '.join(job.get('matches', [])))
            st.caption('Source: ' + str(job.get('source', '')))
            safe_link('Open original job', job.get('url', ''))
            stages = ['New', 'Shortlisted', 'Applied', 'Archived']
            selected = st.selectbox('Application stage', stages, index=stages.index(job.get('stage', 'New')), key='stage_' + job['_id'])
            if selected != job.get('stage', 'New'):
                job['stage'] = selected
                # Explicit user change; put preserves the stage during subsequent scans.
                with store.db() as connection:
                    connection.execute('UPDATE items SET data=? WHERE kind=? AND id=?', (json.dumps(job), 'job', job['_id']))
    if not records:
        st.info('No saved jobs yet. Connect Adzuna or add a job feed, then scan.')
    alerts = store.items('job_alert')
    if alerts:
        st.subheader('Job alerts from your email')
        for alert in alerts[:30]:
            st.write(alert['subject'])
            st.caption(alert['preview'])
            safe_link('Open alert', alert['url'])

with inbox:
    st.subheader('Gmail + Outlook')
    st.caption('Scans up to 50 recent messages per connected account. Gmail uses a 30-day query; Outlook uses the latest 50. Full message bodies and attachments are not downloaded.')
    if st.button('Scan connected inboxes now'):
        run_scan(agents.scan_inbox)
    for mail in store.items('mail')[:100]:
        with st.expander(mail['provider'].title() + ' · ' + mail['subject']):
            st.text(mail['sender'])
            st.text(mail['date'])
            st.text(mail['preview'])
            safe_link('Open original email', mail['url'])

with subscriptions:
    st.subheader('Subscription signals')
    st.caption('These are leads from email wording, not verified bank charges. The scanner never treats email instructions as authorization.')
    for row in store.items('subscription'):
        with st.expander(row['merchant'] + ' · ' + row['subject']):
            st.text(row['preview'])
            st.caption(row['status'])
            safe_link('Review original email', row['url'])
    st.subheader('Prepare a cancellation request')
    st.caption('Verify the service’s support address from its official website. This creates a reviewable action; it does not send yet. Services requiring account-portal cancellation must be completed in that portal.')
    with st.form('cancellation'):
        provider = st.selectbox('Send from', ['gmail', 'outlook'])
        merchant = st.text_input('Service to cancel')
        recipient = st.text_input('Verified cancellation/support email')
        body = st.text_area('Exact message', 'Please cancel my subscription and stop future renewals. Please confirm the cancellation and its effective date by email.')
        if st.form_submit_button('Create cancellation action'):
            try:
                agents.propose_cancellation(provider, merchant, recipient, body)
                st.success('Saved for review in Actions. Nothing has been sent.')
            except ValueError as error:
                st.error(str(error))

with actions:
    st.subheader('Action queue')
    st.caption('Review the exact destination and message. Once approved, the worker sends it automatically when agents are enabled. Cancellation is only confirmed by the provider, not by sending an email.')
    for action in store.actions():
        payload = action['payload']
        with st.expander(f"#{action['id']} · {payload['merchant']} · {action['state']}"):
            st.text(f"From: {payload['provider']}\nTo: {payload['recipient']}\nSubject: {payload['subject']}")
            st.text(payload['body'])
            st.caption(action['detail'])
            if action['state'] == 'pending':
                reviewed = st.checkbox('I checked this recipient, service and message', key='review_' + str(action['id']))
                if st.button('Approve this exact email', key='approve_' + str(action['id']), disabled=not reviewed):
                    agents.approve(action['id'])
                    st.rerun()
            if action['state'] in ('pending', 'approved'):
                if st.button('Reject / revoke', key='reject_' + str(action['id'])):
                    agents.reject(action['id'])
                    st.rerun()
            if action['state'] in ('sending', 'delivery_uncertain'):
                st.warning('Delivery is uncertain or in progress. Check Sent mail before making another request; this app will not retry automatically.')
    if st.button('Execute approved actions now', disabled=store.setting('paused', True)):
        run_scan(agents.execute_approved)

with settings:
    st.subheader('Job search and personal context')
    current = store.setting('jobs', {})
    with st.form('job_settings'):
        location = st.text_input('Location for Adzuna searches', current.get('location', 'Melbourne'))
        queries = st.text_area('Search phrases, one per line (maximum 5)', current.get('queries', 'marketing\nsocial media\nproduct manager'))
        keywords = st.text_input('Ranking terms, comma separated', current.get('keywords', 'marketing,social media,product,communications'))
        feeds = st.text_area('Public HTTPS job RSS/Atom feeds, one per line (maximum 10)', current.get('feeds', ''))
        background = st.text_area('Your resume, preferences and context (saved on this computer)', store.setting('background', ''))
        if st.form_submit_button('Save search settings'):
            store.save_setting('jobs', dict(location=location, queries=queries, keywords=keywords, feeds=feeds))
            store.save_setting('background', background)
            st.success('Saved locally.')
    with st.expander('Adzuna Australia connection'):
        st.markdown('Register your app at [Adzuna](https://developer.adzuna.com/). Provider limits and terms apply.')
        with st.form('adzuna'):
            app_id = st.text_input('Adzuna app ID', type='password')
            app_key = st.text_input('Adzuna app key', type='password')
            if st.form_submit_button('Store Adzuna credentials'):
                try:
                    if not app_id or not app_key:
                        raise ValueError('Both fields are required.')
                    accounts.save_secret('adzuna_id', app_id)
                    accounts.save_secret('adzuna_key', app_key)
                    st.success('Stored in your OS credential vault.')
                except Exception:
                    st.error('Could not save credentials. Ensure your OS credential vault is available.')
    st.subheader('Email connections')
    st.caption('Connect your own registered OAuth apps. ChatGPT’s connected accounts are separate. Read access is requested first; sending is optional.')
    with st.expander('Connect Gmail', expanded=False):
        st.write('Status:', 'Connected' if store.setting('gmail_connected', False) else 'Not connected')
        st.markdown('Enable Gmail API, create a Desktop OAuth client, and add your account as a test user. See SETUP.md.')
        config = st.file_uploader('Google Desktop client JSON (never committed)', type='json')
        gmail_send = st.checkbox('Also allow sending reviewed cancellation emails', key='gmail_send')
        if st.button('Connect Gmail on this computer', disabled=config is None):
            try:
                with st.spinner('Complete Google sign-in in the browser opened on this computer…'):
                    accounts.connect_gmail(config.getvalue().decode(), gmail_send)
                st.success('Gmail connected.')
            except Exception:
                st.error('Gmail connection failed. Check Desktop client JSON, consent-screen test users and access scopes.')
        if st.button('Disconnect Gmail locally'):
            try:
                accounts.disconnect('gmail')
                st.success('Local Gmail credentials removed. You can also revoke app access in your Google account.')
            except Exception:
                st.error('Could not access OS credential vault.')
    with st.expander('Connect Outlook / Hotmail', expanded=False):
        st.write('Status:', 'Connected' if store.setting('outlook_connected', False) else 'Not connected')
        client_id = st.text_input('Microsoft public application client ID', store.setting('microsoft_client_id', ''))
        outlook_send = st.checkbox('Also allow sending reviewed cancellation emails', key='outlook_send')
        if st.button('Start Outlook sign-in'):
            try:
                store.save_setting('microsoft_client_id', client_id.strip())
                flow, scopes = accounts.begin_outlook(outlook_send)
                st.session_state['outlook_flow'] = (flow, scopes)
            except Exception:
                st.error('Could not start Microsoft sign-in. Enable public client flows in your app registration.')
        if 'outlook_flow' in st.session_state:
            flow, scopes = st.session_state['outlook_flow']
            st.text(flow.get('message', ''))
            if st.button('I completed Microsoft sign-in'):
                try:
                    with st.spinner('Finishing sign-in…'):
                        accounts.finish_outlook(flow, scopes)
                    del st.session_state['outlook_flow']
                    st.success('Outlook connected.')
                except Exception:
                    st.error('Sign-in failed or expired. Start sign-in again.')
        if st.button('Disconnect Outlook locally'):
            try:
                accounts.disconnect('outlook')
                st.success('Local Outlook credentials removed. Revoke app access in your Microsoft account if needed.')
            except Exception:
                st.error('Could not access OS credential vault.')
    st.subheader('Autonomous schedule')
    schedule = store.setting('schedule', {})
    with st.form('schedule'):
        auto_jobs = st.checkbox('Run job scout automatically', schedule.get('jobs', False))
        auto_mail = st.checkbox('Run inbox and subscription scanners automatically', schedule.get('mail', False))
        minutes = st.number_input('Minutes between scans', min_value=15, max_value=1440, value=int(schedule.get('minutes', 60)))
        if st.form_submit_button('Save schedule'):
            store.save_setting('schedule', dict(jobs=auto_jobs, mail=auto_mail, minutes=minutes))
            st.success('Schedule saved. Enable agent actions and keep worker.py running.')

with activity:
    st.subheader('Activity log')
    if st.button('Refresh activity'):
        st.rerun()
    st.dataframe(store.events(), use_container_width=True)
