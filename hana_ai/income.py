"""Income evidence is kept separate from unvalidated service ideas."""
import hashlib
import re
from datetime import datetime, timezone

from hana_ai.store import event, items, put, setting


def payment_evidence(text):
    pattern = r'(?P<currency>AUD\s*|A\$\s*|AU\$\s*|\$\s*)(?P<amount>\d[\d,]*(?:\.\d{1,2})?)(?P<suffix>[^\n.;]{0,40})'
    for match in re.finditer(pattern, text, re.I):
        prefix = text[max(0, match.start() - 10):match.start()]
        currency = 'AUD' if match.group('currency').strip().upper() != '$' else 'unspecified'
        if re.search(r'(US|USD)\s*$', prefix, re.I):
            currency = 'USD'
        amount = float(match.group('amount').replace(',', ''))
        suffix = match.group('suffix').lower()
        if re.search(r'\b(year|annual|annum|pa)\b|/yr|p\.a', suffix):
            basis = 'annual'
        elif re.search(r'\b(hour|hourly|hr)\b|/h\b', suffix):
            basis = 'hourly'
        elif re.search(r'\b(day|daily|shift)\b', suffix):
            basis = 'shift/day'
        elif re.search(r'\b(project|booking|video|deliverable|shoot|session|task)\b', suffix):
            basis = 'project/booking'
        else:
            basis = 'unverified basis'
        return {'amount': amount, 'currency': currency, 'basis': basis, 'quote': match.group(0).strip()}
    return None


def evaluate_lead(row, minimum):
    text = row.get('title', '') + ' ' + row.get('description', row.get('preview', ''))
    if re.search(r'\b(unpaid|commission.only|pay.to.join|survey rewards|crypto trading|forex trading|gambling)\b', text, re.I):
        return None
    payment = payment_evidence(text)
    if payment and payment['basis'] in ('shift/day', 'project/booking') and payment['currency'] == 'AUD' and payment['amount'] < minimum:
        return None
    confirmed_target = bool(payment and payment['currency'] == 'AUD' and payment['basis'] in ('shift/day', 'project/booking') and payment['amount'] >= minimum)
    return dict(row, payment=payment, target_evidence=confirmed_target,
        category='Advertised pay meets target' if confirmed_target else 'Pay verification needed',
        expenses='Unknown: verify before accepting', payment_date='Not stated: check payment terms',
        next_action='Check original listing, eligibility, expenses and payment date before applying.',
        checked=datetime.now(timezone.utc).isoformat(), stage='New')


def service_ideas(profile):
    """Suggested offers, never represented as real clients or confirmed earnings."""
    packages = [
        ('ugc', ('ugc', 'content', 'modelling', 'modeling'), 'One short product video', 250,
         'Offer one edited product video with one revision. Quote usage rights separately. Use existing equipment and a relevant portfolio sample.'),
        ('marketing', ('marketing', 'social media', 'communications'), 'Express social media audit', 300,
         'Offer a focused audit and five prioritised improvements for a small business. Define the deliverable and revision limit before quoting.'),
        ('art', ('art', 'painting', 'artist'), 'Small original artwork commission', 350,
         'Offer one clearly sized original artwork using materials already available. Agree the brief, materials cost and deposit before starting.'),
    ]
    result = []
    for identity, terms, title, suggested, detail in packages:
        if not any(term in profile.lower() for term in terms):
            continue
        result.append({'id': identity, 'title': title, 'suggested_quote_aud': suggested, 'detail': detail,
            'evidence': 'Business idea only. Suggested quote is unvalidated; no customer or payment is confirmed.',
            'next_action': 'Prepare a portfolio sample and a specific offer. Review any pitch before sending.'})
    return result


def scan_income():
    from hana_ai.agents import scan_jobs
    config = setting('income_search', {})
    search = {'location': config.get('location', 'Melbourne'),
              'queries': config.get('queries', 'brand ambassador\nevent staff\ncontent creator\nfreelance marketing\nmodel'),
              'keywords': config.get('keywords', 'paid,casual,freelance,content,event'),
              'feeds': config.get('feeds', ''), 'remote': config.get('remote', True)}
    result = scan_jobs(search, record_kind='income_lead')
    leads = items('income_lead')
    terms = re.compile(r'\b(paid opportunity|casting|ugc|brand ambassador|freelance|paid shoot|event staff)\b', re.I)
    for mail in items('mail'):
        if terms.search(mail['subject'] + ' ' + mail['preview']):
            leads.append({'title': mail['subject'], 'description': mail['preview'], 'url': mail['url'],
                          'source': mail['provider'] + ' email', 'company': mail['sender']})
    count = 0
    for row in leads:
        evaluated = evaluate_lead(row, float(config.get('minimum', 100)))
        if evaluated:
            identity = hashlib.sha256(row['url'].encode()).hexdigest()
            count += put('income', identity, evaluated)
    for idea in service_ideas(setting('background', '')):
        put('idea', idea['id'], idea)
    result['new_income_leads'] = count
    result['verified_payment_warning'] = 'Advertised pay is not guaranteed take-home earnings. Fees, costs and payment timing require verification.'
    event('Income scout', 'ok' if leads else 'warning', f'{count} new leads; {result["sources"]} source queries; {len(result["errors"])} source errors')
    return result
