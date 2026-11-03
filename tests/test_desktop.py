import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from hana_ai import store
from hana_ai.desktop_ui import Window


@pytest.fixture(scope='session')
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def window(tmp_path, monkeypatch, qt_app):
    monkeypatch.setenv('HANA_DATA_DIR', str(tmp_path))
    view = Window(background=False)
    yield view
    view._closing = True
    view.live.stop()
    view.scheduler.stop()
    view.tray.hide()
    view.close()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_native_pages_and_live_timer(window):
    assert window.pages.count() == 9
    assert window.live.isActive()
    assert not window.scheduler.isActive()
    assert window.windowTitle() == 'Hana AI'


def test_native_pause_persists(window):
    window.enable.setChecked(True)
    assert not store.setting('paused')
    window.enable.setChecked(False)
    assert store.setting('paused')


def test_money_view_updates_without_reopening(window):
    store.put('income', 'one', {'title': 'Paid shoot', 'payment': {'quote': 'A$300 per booking'}, 'target_evidence': True, 'source': 'test', 'category': 'Advertised pay meets target'})
    window.refresh()
    assert window.money.table.rowCount() == 1
    store.put('income', 'two', {'title': 'Unknown pay', 'payment': None, 'target_evidence': False, 'source': 'test', 'category': 'Pay verification needed'})
    window.refresh()
    assert window.money.table.rowCount() == 2
    window.only_target.setChecked(True)
    assert window.money.table.rowCount() == 1


def test_profile_and_schedule_save(window):
    window.profile.setPlainText('Marketing and UGC')
    window.auto_income.setChecked(True)
    window.save_settings()
    assert store.setting('background') == 'Marketing and UGC'
    assert store.setting('schedule')['income']
