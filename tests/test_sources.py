from unittest.mock import Mock
from hana_ai import sources


def test_public_source_is_cached_and_location_filtered(tmp_path, monkeypatch):
    monkeypatch.setenv('HANA_DATA_DIR', str(tmp_path))
    response = Mock()
    response.json.return_value = {'jobs': [
        {'title': 'Marketing manager', 'url': 'https://remotive.com/one', 'candidate_required_location': 'Worldwide'},
        {'title': 'Marketing lead', 'url': 'https://remotive.com/two', 'candidate_required_location': 'USA Only'}]}
    get = Mock(return_value=response)
    monkeypatch.setattr(sources.requests, 'get', get)
    one, error = sources.remote_jobs(['marketing'])
    two, _ = sources.remote_jobs(['marketing'])
    assert get.call_count == 1
    assert len(one) == len(two) == 1
    assert one[0]['source'] == 'Remotive'
    assert '24 hours' in one[0]['freshness']
