from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_dashboard_starts_without_accounts_or_model(tmp_path, monkeypatch):
    monkeypatch.setenv('HANA_DATA_DIR', str(tmp_path))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == '✨ Hana AI'
    assert len(app.tabs) == 7
    assert app.chat_input[0].disabled


def test_pause_toggle_and_settings_persist(tmp_path, monkeypatch):
    from hana_ai import store
    monkeypatch.setenv('HANA_DATA_DIR', str(tmp_path))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
    app.toggle[0].set_value(True).run()
    assert not store.setting('paused')
    next(b for b in app.button if b.label == '⏸ Pause all agents').click().run()
    assert store.setting('paused')
    assert not app.exception
