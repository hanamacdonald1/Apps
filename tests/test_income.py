from hana_ai import income, store


def test_rejects_microtasks_and_unpaid_offers():
    assert income.evaluate_lead({'title': 'UGC shoot AUD 5 per video'}, 100) is None
    assert income.evaluate_lead({'title': 'Unpaid model shoot'}, 100) is None


def test_explicit_per_project_pay_can_meet_target():
    row = income.evaluate_lead({'title': 'Product shoot A$350 per booking'}, 100)
    assert row['target_evidence']
    assert row['payment']['basis'] == 'project/booking'
    assert row['payment_date'].startswith('Not stated')


def test_hourly_annual_and_unknown_currency_are_not_guaranteed_quick_income():
    for title in ['Role AUD 100000 per year', 'Shift AUD 40 per hour', 'Project $350 per project']:
        assert not income.evaluate_lead({'title': title}, 100)['target_evidence']


def test_business_ideas_are_not_paid_listings():
    ideas = income.service_ideas('UGC and social media marketing')
    assert len(ideas) == 2
    assert all('no customer or payment is confirmed' in idea['evidence'] for idea in ideas)
    assert income.service_ideas('') == []


def test_income_scout_uses_real_saved_evidence(tmp_path, monkeypatch):
    from hana_ai import agents
    monkeypatch.setenv('HANA_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(agents, 'scan_jobs', lambda *a, **k: {'sources': 0, 'errors': []})
    store.put('income_lead', 'one', {'title': 'Product content A$300 per video', 'url': 'https://example.com/brief', 'source': 'test source'})
    store.save_setting('background', 'Content creator and marketing')
    result = income.scan_income()
    assert result['new_income_leads'] == 1
    assert store.items('income')[0]['target_evidence']
    assert store.items('idea')
