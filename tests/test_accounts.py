import base64
from email import message_from_bytes
from unittest.mock import Mock

import pytest

from hana_ai import accounts


def test_gmail_preserves_reviewed_recipient_and_body(monkeypatch):
    service = Mock()
    monkeypatch.setattr(accounts, 'gmail', lambda: service)
    accounts.send_mail('gmail', 'support@example.com', 'Cancel Example', 'Please cancel my plan.')
    args = service.users().messages().send.call_args.kwargs
    message = message_from_bytes(base64.urlsafe_b64decode(args['body']['raw']))
    assert message['To'] == 'support@example.com'
    assert message['Subject'] == 'Cancel Example'
    assert message.get_payload().strip() == 'Please cancel my plan.'


def test_outlook_requests_save_to_sent_items(monkeypatch):
    monkeypatch.setattr(accounts, 'outlook_token', lambda: 'test-only-token')
    post = Mock()
    monkeypatch.setattr(accounts.requests, 'post', post)
    accounts.send_mail('outlook', 'support@example.com', 'Cancel Example', 'Please cancel.')
    kwargs = post.call_args.kwargs
    assert kwargs['json']['saveToSentItems'] is True
    assert kwargs['json']['message']['toRecipients'][0]['emailAddress']['address'] == 'support@example.com'


def test_header_injection_rejected_before_provider_call(monkeypatch):
    provider = Mock()
    monkeypatch.setattr(accounts, 'gmail', provider)
    with pytest.raises(ValueError):
        accounts.send_mail('gmail', 'support@example.com', 'Cancel\nBcc: other@example.com', 'Body')
    provider.assert_not_called()
