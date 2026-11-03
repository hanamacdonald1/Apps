"""Public job source with a shared six-hour request budget."""
import json
import time
import requests
from hana_ai.store import db, save_setting, setting


def remote_jobs(queries):
    now = time.time()
    with db() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute("SELECT value FROM settings WHERE key='remotive_next'").fetchone()
        refresh = not row or json.loads(row[0]) <= now
        if refresh:
            connection.execute("INSERT OR REPLACE INTO settings VALUES ('remotive_next',?)", (json.dumps(now + 21600),))
    if refresh:
        try:
            result = requests.get('https://remotive.com/api/remote-jobs', params={'limit': 500}, timeout=30)
            result.raise_for_status()
            rows = result.json()['jobs']
            save_setting('remotive_cache', {'jobs': rows, 'fetched': now})
            save_setting('remotive_error', '')
        except (requests.RequestException, ValueError, KeyError):
            save_setting('remotive_error', 'Remotive fetch failed; cached data may be stale. The next fetch respects the six-hour source limit.')
    cache = setting('remotive_cache', {'jobs': [], 'fetched': None})
    terms = [q.strip().lower() for q in queries if q.strip()]
    rows = []
    for job in cache['jobs']:
        location = job.get('candidate_required_location', '')
        if not any(term in location.lower() for term in ['worldwide', 'australia', 'oceania', 'apac']):
            continue
        text = (job.get('title', '') + ' ' + job.get('description', '')).lower()
        if not any(term in text for term in terms):
            continue
        rows.append({'title': job['title'], 'company': job.get('company_name', ''),
            'url': job['url'], 'description': job.get('description', ''), 'location': location,
            'posted': job.get('publication_date', ''), 'source': 'Remotive',
            'salary_note': job.get('salary', '') + ' (currency and period must be verified)',
            'fetched': cache['fetched'],
            'freshness': 'Remotive public listings are delayed by 24 hours; app refreshes this source at most every six hours. Check original listing and eligibility.'})
    return rows, setting('remotive_error', '')
