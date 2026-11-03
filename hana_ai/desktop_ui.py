"""Qt desktop app. Worker threads never manipulate widgets directly."""
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PySide6.QtCore import QLockFile, QObject, QRunnable, QThreadPool, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter, QStackedWidget,
    QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from hana_ai import accounts, agents, income, store


class Signals(QObject):
    done = Signal(str, object)
    failed = Signal(str)
    progress = Signal(str, str)


class Task(QRunnable):
    def __init__(self, name, function):
        super().__init__()
        self.name, self.function, self.signals = name, function, Signals()

    def run(self):
        try:
            result = self.function(lambda text: self.signals.progress.emit(self.name, text))
            self.signals.done.emit(self.name, result)
        except Exception:
            # Never expose provider exceptions, which may contain tokens or private content.
            self.signals.failed.emit(self.name)


def icon():
    image = QPixmap(64, 64)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor('#e8a6bb'))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(1, 1, 62, 62, 18, 18)
    painter.setPen(QColor('#201b28'))
    font = painter.font()
    font.setPixelSize(36)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, 'H')
    painter.end()
    return QIcon(image)


def open_url(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
            QDesktopServices.openUrl(QUrl(url))
    except ValueError:
        return


def button(text, callback, layout):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    layout.addWidget(widget)
    return widget


def plain(text):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class Records(QWidget):
    def __init__(self, headers, fields, detail=None):
        super().__init__()
        self.fields, self.rows, self.detail = fields, [], detail
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.selected)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(230)
        layout.addWidget(self.table)
        layout.addWidget(self.text)
        button('Open original source', self.open_selected, layout)
        self._last = None

    def current(self):
        index = self.table.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def update_rows(self, rows):
        fingerprint = json.dumps(rows, sort_keys=True)
        if fingerprint == self._last:
            return
        selected = self.current()
        identity = selected.get('_id', selected.get('id')) if selected else None
        self._last, self.rows = fingerprint, rows
        self.table.setRowCount(len(rows))
        select_index = None
        for index, row in enumerate(rows):
            for column, field in enumerate(self.fields):
                value = field(row) if callable(field) else row.get(field, '')
                self.table.setItem(index, column, QTableWidgetItem(str(value or '')))
            if row.get('_id', row.get('id')) == identity:
                select_index = index
        if select_index is not None:
            self.table.selectRow(select_index)
        elif rows:
            self.table.selectRow(0)
        else:
            self.text.clear()

    def selected(self):
        row = self.current()
        if row:
            self.text.setPlainText(self.detail(row) if self.detail else json.dumps(row, indent=2, ensure_ascii=False))

    def open_selected(self):
        row = self.current()
        if row:
            open_url(row.get('url', ''))


class Window(QMainWindow):
    def __init__(self, background=True):
        super().__init__()
        self.setWindowTitle('Hana AI')
        self.setWindowIcon(icon())
        self.resize(1200, 820)
        self.pool = QThreadPool.globalInstance()
        self.tasks, self.messages = {}, []
        self.last_event = 0
        self._closing = False
        current_jobs = store.setting('jobs', {})
        if 'remote' not in current_jobs:
            current_jobs['remote'] = True
            store.save_setting('jobs', current_jobs)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        top = QHBoxLayout()
        title = QLabel('Hana AI')
        title.setObjectName('brand')
        top.addWidget(title)
        self.status = plain('Ready. Connect your sources in Settings.')
        top.addWidget(self.status, 1)
        self.enable = QCheckBox('Agents enabled')
        self.enable.setChecked(not store.setting('paused', True))
        self.enable.toggled.connect(self.set_enabled)
        top.addWidget(self.enable)
        button('Pause all', lambda: self.enable.setChecked(False), top)
        layout.addLayout(top)
        body = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setFixedWidth(205)
        self.pages = QStackedWidget()
        body.addWidget(self.nav)
        body.addWidget(self.pages, 1)
        layout.addLayout(body, 1)
        self.make_today()
        self.make_chat()
        self.make_money()
        self.make_jobs()
        self.make_inbox()
        self.make_subscriptions()
        self.make_actions()
        self.make_activity()
        self.make_settings()
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.tray = QSystemTrayIcon(icon(), self)
        menu = QMenu()
        show = menu.addAction('Open Hana AI')
        show.triggered.connect(self.show_window)
        pause = menu.addAction('Pause agents')
        pause.triggered.connect(lambda: self.enable.setChecked(False))
        quit_action = menu.addAction('Quit Hana AI')
        quit_action.triggered.connect(self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.live = QTimer(self)
        self.live.timeout.connect(self.refresh)
        self.live.start(2000)
        self.scheduler = QTimer(self)
        self.scheduler.timeout.connect(self.schedule_tick)
        if background:
            self.scheduler.start(10000)
        self.refresh()
        if background:
            self.run('Models', self.model_list)
            QTimer.singleShot(900, self.first_run)

    def page(self, name):
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(name)
        heading.setObjectName('heading')
        layout.addWidget(heading)
        self.nav.addItem(name)
        self.pages.addWidget(page)
        return layout

    def make_today(self):
        layout = self.page('Today')
        self.overview = plain('')
        self.overview.setObjectName('summary')
        layout.addWidget(self.overview)
        layout.addWidget(plain('Start with one useful action. Scans use your configured sources; no sample opportunities are shown.'))
        button('Find paid opportunities', lambda: self.run('Income scout', lambda p: income.scan_income()), layout)
        button('Find suitable jobs', lambda: self.run('Job scout', lambda p: agents.scan_jobs()), layout)
        button('Review connected inboxes', lambda: self.run('Inbox scout', lambda p: agents.scan_inbox()), layout)
        self.today_activity = QTextEdit()
        self.today_activity.setReadOnly(True)
        layout.addWidget(self.today_activity)

    def make_chat(self):
        layout = self.page('Assistant')
        layout.addWidget(plain('Ask the coordinator to scan sources, compare opportunities, or draft a pitch. A local tool-capable Ollama model is needed.'))
        row = QHBoxLayout()
        self.model = QComboBox()
        row.addWidget(self.model, 1)
        button('Refresh models', lambda: self.run('Models', self.model_list), row)
        layout.addLayout(row)
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        layout.addWidget(self.chat, 1)
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText('Example: Find opportunities to earn A$300 this week and explain the next step.')
        self.prompt.setMaximumHeight(100)
        layout.addWidget(self.prompt)
        self.send = button('Send to coordinator', self.ask, layout)

    def make_money(self):
        layout = self.page('Money this week')
        layout.addWidget(plain('Target meaningful pay, not microtasks. Advertised pay, payment timing and actual take-home earnings are separate facts.'))
        button('Scan paid opportunities now', lambda: self.run('Income scout', lambda p: income.scan_income()), layout)
        self.only_target = QCheckBox('Only show listings with explicit AUD pay meeting my per-project/day target')
        self.only_target.toggled.connect(self.refresh)
        layout.addWidget(self.only_target)
        self.money = Records(['Opportunity', 'Pay evidence', 'Status', 'Source'], ['title',
            lambda r: (r['payment']['quote'] if r.get('payment') else 'Not stated'), 'category', 'source'])
        layout.addWidget(self.money, 1)
        self.ideas = QTextEdit()
        self.ideas.setReadOnly(True)
        self.ideas.setMaximumHeight(150)
        layout.addWidget(plain('Service ideas you could offer: these have no confirmed customer or income.'))
        layout.addWidget(self.ideas)

    def make_jobs(self):
        layout = self.page('Jobs')
        button('Scan jobs now', lambda: self.run('Job scout', lambda p: agents.scan_jobs()), layout)
        self.jobs = Records(['Role', 'Company', 'Keyword coverage', 'Stage'], ['title', 'company', lambda r: str(r.get('score', 0)) + '%', 'stage'])
        layout.addWidget(self.jobs, 1)
        stages = QHBoxLayout()
        for stage in ['Shortlisted', 'Applied', 'Archived']:
            button('Mark ' + stage, lambda checked=False, value=stage: self.set_job_stage(value), stages)
        layout.addLayout(stages)

    def make_inbox(self):
        layout = self.page('Inbox')
        layout.addWidget(plain('Recent message previews from connected Gmail and Outlook accounts. Open the original to review full details.'))
        button('Scan inboxes now', lambda: self.run('Inbox scout', lambda p: agents.scan_inbox()), layout)
        self.mail = Records(['Account', 'Subject', 'Sender', 'Date'], ['provider', 'subject', 'sender', 'date'])
        layout.addWidget(self.mail, 1)

    def make_subscriptions(self):
        layout = self.page('Subscriptions')
        layout.addWidget(plain('Possible subscriptions from email wording. Verify the original message and the service’s official cancellation route.'))
        self.subs = Records(['Service signal', 'Subject', 'Account'], ['merchant', 'subject', 'provider'])
        layout.addWidget(self.subs, 1)
        form = QFormLayout()
        self.cancel_provider = QComboBox()
        self.cancel_provider.addItems(['gmail', 'outlook'])
        self.merchant, self.recipient = QLineEdit(), QLineEdit()
        self.cancel_body = QTextEdit('Please cancel my subscription and stop future renewals. Please confirm the cancellation and its effective date by email.')
        self.cancel_body.setMaximumHeight(85)
        form.addRow('Send from', self.cancel_provider)
        form.addRow('Service', self.merchant)
        form.addRow('Verified support email', self.recipient)
        form.addRow('Exact request', self.cancel_body)
        layout.addLayout(form)
        button('Prepare request for review', self.propose, layout)

    def make_actions(self):
        layout = self.page('Actions')
        layout.addWidget(plain('Approvals apply to the exact displayed destination and message. Sending a request does not confirm cancellation. Portal cancellation is not automated in this version.'))
        self.action_records = Records(['ID', 'Service', 'State'], ['id', lambda r: r['payload']['merchant'], 'state'])
        layout.addWidget(self.action_records, 1)
        row = QHBoxLayout()
        button('Review and approve selected', self.approve_selected, row)
        button('Revoke selected', self.revoke_selected, row)
        button('Run approved actions', lambda: self.run('Approved actions', lambda p: agents.execute_approved()), row)
        layout.addLayout(row)

    def make_activity(self):
        layout = self.page('Activity')
        layout.addWidget(plain('Updates automatically. Connection failures and missing sources remain visible here.'))
        self.activity = Records(['Time', 'Agent', 'State'], ['created', 'agent', 'status'])
        layout.addWidget(self.activity)

    def make_settings(self):
        layout = self.page('Settings')
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        self.profile = QTextEdit(store.setting('background', ''))
        self.profile.setPlaceholderText('Your skills, resume text, availability, equipment and transport.')
        self.profile.setMaximumHeight(130)
        form.addRow('My profile / resume', self.profile)
        import_button = QPushButton('Import resume PDF or text')
        import_button.clicked.connect(self.import_resume)
        form.addRow('', import_button)
        config = store.setting('jobs', {})
        self.location = QLineEdit(config.get('location', 'Melbourne'))
        self.queries = QTextEdit(config.get('queries', 'marketing\nsocial media\nproduct manager'))
        self.queries.setMaximumHeight(90)
        self.keywords = QLineEdit(config.get('keywords', 'marketing,social media,product,communications'))
        self.feeds = QTextEdit(config.get('feeds', ''))
        self.feeds.setMaximumHeight(70)
        form.addRow('Job location', self.location)
        form.addRow('Job phrases, one per line (5 max)', self.queries)
        form.addRow('Ranking terms, comma separated', self.keywords)
        form.addRow('Public HTTPS job feeds', self.feeds)
        self.remote_source = QCheckBox('Include Australia / worldwide remote roles from Remotive (no API key)')
        self.remote_source.setChecked(config.get('remote', True))
        form.addRow('Built-in job source', self.remote_source)
        form.addRow('', plain('Remotive listings are delayed by 24 hours and cached for six hours. Original links and source names are retained. Verify geographic eligibility in each ad.'))
        income_config = store.setting('income_search', {})
        self.income_queries = QTextEdit(income_config.get('queries', 'brand ambassador\nevent staff\ncontent creator\nfreelance marketing\nmodel'))
        self.income_queries.setMaximumHeight(90)
        self.income_feeds = QTextEdit(income_config.get('feeds', ''))
        self.income_feeds.setMaximumHeight(70)
        self.minimum = QSpinBox()
        self.minimum.setRange(100, 100000)
        self.minimum.setValue(int(income_config.get('minimum', 100)))
        form.addRow('Income search phrases (5 max)', self.income_queries)
        form.addRow('Income opportunity feeds', self.income_feeds)
        form.addRow('Minimum AUD per project/day', self.minimum)
        schedule = store.setting('schedule', {})
        self.auto_jobs, self.auto_mail, self.auto_income = QCheckBox('Jobs'), QCheckBox('Inbox'), QCheckBox('Income')
        for key, box in [('jobs', self.auto_jobs), ('mail', self.auto_mail), ('income', self.auto_income)]:
            box.setChecked(schedule.get(key, False))
            form.addRow('Autonomous scans', box)
        self.interval = QSpinBox()
        self.interval.setRange(15, 1440)
        self.interval.setValue(int(schedule.get('minutes', 60)))
        form.addRow('Minutes between scans', self.interval)
        self.notifications = QCheckBox('Notify me about completed scans (no private email previews)')
        self.notifications.setChecked(store.setting('notifications', True))
        form.addRow('Desktop notifications', self.notifications)
        self.quiet_start, self.quiet_end = QSpinBox(), QSpinBox()
        for widget in [self.quiet_start, self.quiet_end]:
            widget.setRange(0, 23)
        self.quiet_start.setValue(store.setting('quiet_start', 22))
        self.quiet_end.setValue(store.setting('quiet_end', 8))
        form.addRow('Quiet hours start (local hour)', self.quiet_start)
        form.addRow('Quiet hours end (same = disabled)', self.quiet_end)
        self.theme = QComboBox()
        self.theme.addItems(['Dark', 'Light'])
        self.theme.setCurrentText(store.setting('theme', 'Dark'))
        form.addRow('Theme', self.theme)
        save = QPushButton('Save preferences and schedule')
        save.clicked.connect(self.save_settings)
        form.addRow('', save)
        self.adzuna_id, self.adzuna_key = QLineEdit(), QLineEdit()
        for widget in [self.adzuna_id, self.adzuna_key]:
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Adzuna app ID', self.adzuna_id)
        form.addRow('Adzuna key', self.adzuna_key)
        save_keys = QPushButton('Save job-source credentials to OS vault')
        save_keys.clicked.connect(self.save_keys)
        form.addRow('', save_keys)
        adzuna_link = QPushButton('Open Adzuna registration')
        adzuna_link.clicked.connect(lambda: open_url('https://developer.adzuna.com/'))
        form.addRow('', adzuna_link)
        self.allow_send = QCheckBox('Request permission to send reviewed cancellation emails')
        form.addRow('Email permissions', self.allow_send)
        google = QPushButton('Connect Gmail using Desktop OAuth JSON')
        google.clicked.connect(self.connect_google)
        form.addRow('', google)
        self.microsoft_id = QLineEdit(store.setting('microsoft_client_id', ''))
        form.addRow('Microsoft public client ID', self.microsoft_id)
        microsoft = QPushButton('Connect Outlook / Hotmail')
        microsoft.clicked.connect(self.connect_microsoft)
        form.addRow('', microsoft)
        for provider in ['gmail', 'outlook']:
            disconnect = QPushButton('Disconnect ' + provider.title() + ' locally')
            disconnect.clicked.connect(lambda checked=False, p=provider: self.run('Disconnect ' + p, lambda progress: accounts.disconnect(p)))
            form.addRow('', disconnect)
        self.connection_label = plain('')
        form.addRow('Connections', self.connection_label)
        ollama = QPushButton('Open official Ollama download')
        ollama.clicked.connect(lambda: open_url('https://ollama.com/download'))
        form.addRow('', ollama)
        self.pull = QPushButton('Download qwen3:4b with installed Ollama')
        self.pull.clicked.connect(self.pull_model)
        form.addRow('', self.pull)
        export = QPushButton('Export local records to JSON')
        export.clicked.connect(self.export_data)
        form.addRow('', export)
        delete = QPushButton('Delete saved local records')
        delete.clicked.connect(self.delete_data)
        form.addRow('', delete)
        form.addRow('', plain('OAuth tokens and keys use the OS credential vault. Local previews and notes are saved on this computer. Google/Microsoft app registration is required.'))
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def set_enabled(self, enabled):
        store.save_setting('paused', not enabled)
        self.status.setText('Agents enabled.' if enabled else 'Paused. An in-flight request may still finish.')

    def run(self, name, function):
        if name in self.tasks:
            self.status.setText(name + ' is already running.')
            return
        task = Task(name, function)
        task.signals.done.connect(self.completed)
        task.signals.failed.connect(self.failed)
        task.signals.progress.connect(self.progress)
        self.tasks[name] = task
        if name != 'Background':
            self.status.setText(name + ' started…')
        self.pool.start(task)

    @Slot(str, str)
    def progress(self, name, text):
        self.status.setText(name + ': ' + text)

    @Slot(str)
    def failed(self, name):
        self.tasks.pop(name, None)
        store.event(name, 'error', 'Task failed. Check connections, credentials and model availability.')
        self.status.setText(name + ' failed. Check Settings and Activity.')
        if name == 'Assistant':
            self.send.setEnabled(True)
            if self.messages and self.messages[-1]['role'] == 'user':
                self.messages.pop()
        self.refresh()

    @Slot(str, object)
    def completed(self, name, result):
        self.tasks.pop(name, None)
        if name == 'Models':
            selected = self.model.currentText() or store.setting('model', '')
            self.model.clear()
            self.model.addItems(result)
            if selected in result:
                self.model.setCurrentText(selected)
            self.status.setText('Local models ready.' if result else 'No local model found. Use Settings to install Ollama and download a model.')
        elif name == 'Assistant':
            answer, trace = result
            self.messages.append({'role': 'assistant', 'content': answer})
            self.chat.append('')
            self.chat.insertPlainText('Hana AI: ' + answer + '\nTools: ' + ', '.join(trace) + '\n')
            self.send.setEnabled(True)
            self.status.setText('Assistant finished.')
        elif name == 'Outlook start':
            flow, scopes = result
            dialog = QMessageBox(self)
            dialog.setWindowTitle('Connect Outlook')
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            dialog.setText(flow.get('message', 'Complete Microsoft sign-in.'))
            dialog.setInformativeText('Complete sign-in in your browser, then click OK. Cancel to stop.')
            dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            open_url(flow.get('verification_uri', 'https://microsoft.com/devicelogin'))
            if dialog.exec() == QMessageBox.StandardButton.Ok:
                self.run('Outlook connect', lambda progress: accounts.finish_outlook(flow, scopes))
        elif name != 'Background':
            self.status.setText(name + ' finished. See Activity for source results and errors.')
            if isinstance(result, dict) and (result.get('errors') or result.get('sources') == 0):
                self.status.setText(name + ': missing sources or connection errors. Check Settings and Activity.')
        self.refresh()

    def model_list(self, progress):
        try:
            response = requests.get('http://127.0.0.1:11434/api/tags', timeout=3)
            response.raise_for_status()
            return [r['name'] for r in response.json().get('models', [])]
        except (requests.RequestException, ValueError):
            return []

    def ask(self):
        text, model = self.prompt.toPlainText().strip(), self.model.currentText()
        if not text or not model:
            self.status.setText('Choose an installed model and enter your request.')
            return
        self.messages.append({'role': 'user', 'content': text})
        self.chat.insertPlainText('\nYou: ' + text + '\n')
        self.prompt.clear()
        self.send.setEnabled(False)
        store.save_setting('model', model)
        self.run('Assistant', lambda progress: agents.agent_chat(model, self.messages.copy(), store.setting('background', ''), progress))

    def schedule_tick(self):
        if 'Background' not in self.tasks:
            self.run('Background', lambda progress: agents.tick())

    def set_job_stage(self, stage):
        row = self.jobs.current()
        if row:
            row['stage'] = stage
            with store.db() as connection:
                connection.execute('UPDATE items SET data=? WHERE kind=? AND id=?', (json.dumps(row), 'job', row['_id']))
            self.refresh()

    def propose(self):
        try:
            agents.propose_cancellation(self.cancel_provider.currentText(), self.merchant.text(), self.recipient.text(), self.cancel_body.toPlainText())
            self.status.setText('Cancellation request prepared. Review it in Actions.')
            self.refresh()
        except ValueError as error:
            QMessageBox.warning(self, 'Check request', str(error))

    def approve_selected(self):
        row = self.action_records.current()
        if not row or row['state'] != 'pending':
            return
        payload = row['payload']
        dialog = QMessageBox(self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setWindowTitle('Approve this exact cancellation email')
        dialog.setText(f"From: {payload['provider']}\nTo: {payload['recipient']}\nSubject: {payload['subject']}\n\n{payload['body']}")
        dialog.setInformativeText('Approve submission when agents are enabled? This does not guarantee cancellation.')
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        if dialog.exec() == QMessageBox.StandardButton.Yes:
            agents.approve(row['id'])
            self.refresh()

    def revoke_selected(self):
        row = self.action_records.current()
        if row:
            agents.reject(row['id'])
            self.refresh()

    def save_settings(self):
        store.save_setting('background', self.profile.toPlainText())
        store.save_setting('jobs', {'location': self.location.text(), 'queries': self.queries.toPlainText(),
            'keywords': self.keywords.text(), 'feeds': self.feeds.toPlainText(), 'remote': self.remote_source.isChecked()})
        store.save_setting('income_search', {'location': self.location.text(), 'queries': self.income_queries.toPlainText(),
            'feeds': self.income_feeds.toPlainText(), 'minimum': self.minimum.value(), 'remote': self.remote_source.isChecked()})
        store.save_setting('schedule', {'jobs': self.auto_jobs.isChecked(), 'mail': self.auto_mail.isChecked(),
            'income': self.auto_income.isChecked(), 'minutes': self.interval.value()})
        for name, value in [('notifications', self.notifications.isChecked()), ('quiet_start', self.quiet_start.value()),
                            ('quiet_end', self.quiet_end.value()), ('theme', self.theme.currentText())]:
            store.save_setting(name, value)
        apply_theme(QApplication.instance(), self.theme.currentText())
        self.status.setText('Preferences and schedule saved.')

    def save_keys(self):
        app_id, key = self.adzuna_id.text().strip(), self.adzuna_key.text().strip()
        if not app_id or not key:
            self.status.setText('Enter both Adzuna credentials.')
            return
        def save(progress):
            accounts.save_secret('adzuna_id', app_id)
            accounts.save_secret('adzuna_key', key)
        self.run('Job credentials', save)
        self.adzuna_id.clear()
        self.adzuna_key.clear()

    def connect_google(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Google Desktop OAuth client', '', 'JSON (*.json)')
        if filename:
            config = Path(filename).read_text(encoding='utf-8-sig')
            allow = self.allow_send.isChecked()
            self.run('Gmail connect', lambda progress: accounts.connect_gmail(config, allow))
            self.status.setText('Complete Google sign-in in the browser that opens.')

    def connect_microsoft(self):
        store.save_setting('microsoft_client_id', self.microsoft_id.text().strip())
        allow = self.allow_send.isChecked()
        self.run('Outlook start', lambda progress: accounts.begin_outlook(allow))

    def import_resume(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Import resume', '', 'Resume (*.pdf *.txt *.md)')
        if not filename:
            return
        try:
            path = Path(filename)
            if path.stat().st_size > 10_000_000:
                raise ValueError('Too large')
            if path.suffix.lower() == '.pdf':
                from pypdf import PdfReader
                text = '\n'.join(page.extract_text() or '' for page in PdfReader(path).pages[:30])
            else:
                text = path.read_text(encoding='utf-8-sig')
            self.profile.setPlainText(text[:100000])
            self.status.setText('Resume imported. Save preferences to use it.')
        except Exception:
            self.status.setText('Could not extract resume text. Try a text PDF or paste the text.')

    def pull_model(self):
        reply = QMessageBox.question(self, 'Download local model', 'Download qwen3:4b using your installed Ollama server? This is a multi-gigabyte download. Progress will show actual totals when supplied by Ollama.')
        if reply != QMessageBox.StandardButton.Yes:
            return
        def pull(progress):
            with requests.post('http://127.0.0.1:11434/api/pull', json={'model': 'qwen3:4b', 'stream': True}, stream=True, timeout=(5, 180)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        value = json.loads(line)
                        if value.get('error'):
                            raise RuntimeError('Model download failed')
                        total, completed = value.get('total', 0), value.get('completed', 0)
                        progress(value.get('status', '') + (f' {completed / 1e9:.2f}/{total / 1e9:.2f} GB' if total else ''))
            return True
        self.run('Model download', pull)

    def export_data(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Export private records', 'hana-ai-export.json', 'JSON (*.json)')
        if filename:
            export = {kind: store.items(kind) for kind in ['job', 'income', 'idea', 'mail', 'subscription']}
            export.update(actions=store.actions(), activity=store.events(), profile=store.setting('background', ''))
            Path(filename).write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding='utf-8')
            self.status.setText('Private records exported to your selected location. OAuth tokens were excluded.')

    def delete_data(self):
        if self.tasks:
            QMessageBox.information(self, 'Wait for tasks', 'Pause agents and wait for running tasks to finish before deleting saved records.')
            return
        reply = QMessageBox.question(self, 'Delete local records', 'Permanently delete saved jobs, email previews, profile, actions and activity? Account tokens remain until you disconnect them.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.enable.setChecked(False)
            with store.db() as connection:
                for table in ['items', 'actions', 'events']:
                    connection.execute('DELETE FROM ' + table)
                connection.execute("DELETE FROM settings WHERE key='background'")
            self.profile.clear()
            self.messages.clear()
            self.chat.clear()
            self.refresh()

    @Slot()
    def refresh(self):
        jobs, leads, mail, subscriptions = store.items('job'), store.items('income'), store.items('mail'), store.items('subscription')
        self.jobs.update_rows(sorted(jobs, key=lambda r: r.get('score', 0), reverse=True))
        if self.only_target.isChecked():
            leads = [row for row in leads if row.get('target_evidence')]
        self.money.update_rows(sorted(leads, key=lambda r: r.get('target_evidence', False), reverse=True))
        self.mail.update_rows(mail)
        self.subs.update_rows(subscriptions)
        self.action_records.update_rows(store.actions())
        events = store.events()
        self.activity.update_rows(events)
        self.overview.setText(f'{len(jobs)} saved jobs     {len(store.items("income"))} income leads     {len(subscriptions)} subscription signals\n' +
            ('Agents paused' if store.setting('paused', True) else 'Agents enabled; scheduled checks run while this app stays open or in the tray.'))
        self.today_activity.setPlainText('\n\n'.join(f"{e['created']} · {e['agent']} · {e['status']}\n{e['detail']}" for e in events[:8]))
        self.ideas.setPlainText('\n\n'.join(f"{i['title']} · suggested quote A${i['suggested_quote_aud']}\n{i['detail']}\n{i['evidence']}" for i in store.items('idea')))
        self.connection_label.setText(' · '.join(p.title() + (': connected' if store.setting(p + '_connected', False) else ': not connected') for p in ['gmail', 'outlook']))
        if events:
            latest = events[0]['id']
            new_scan = any(e['id'] > self.last_event and e['status'] == 'ok' and e['agent'] in ['Job scout', 'Income scout', 'Inbox and subscriptions'] for e in events)
            if self.last_event and new_scan and self.can_notify():
                self.tray.showMessage('Hana AI', 'Your agents have new scan results. Open the app to review them.')
            self.last_event = latest

    def can_notify(self):
        if not self.tray.isVisible() or not store.setting('notifications', True):
            return False
        start, end, hour = store.setting('quiet_start', 22), store.setting('quiet_end', 8), time.localtime().tm_hour
        quiet = (start <= hour < end) if start < end else (hour >= start or hour < end) if start > end else False
        return not quiet

    def first_run(self):
        if store.setting('desktop_onboarded', False):
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle('Welcome to Hana AI')
        dialog.setText('Your desktop agents are ready to configure.')
        dialog.setInformativeText('1. Add your resume and search preferences in Settings.\n2. Connect job sources and Gmail/Outlook using your own OAuth apps.\n3. Install Ollama and download a tool-capable model for chat.\n4. Enable a schedule and agents. Closing the window keeps work running in the tray; Quit stops it.')
        dialog.exec()
        store.save_setting('desktop_onboarded', True)
        self.nav.setCurrentRow(8)

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def closeEvent(self, event):
        if not self._closing and self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()

    def quit_app(self):
        self._closing = True
        self.scheduler.stop()
        self.live.stop()
        self.tray.hide()
        # Exit does not start new work. Interrupted sends remain non-retryable in the database.
        QApplication.instance().quit()


def apply_theme(app, theme):
    dark = theme == 'Dark'
    bg, panel, text, border = ('#17151f', '#25212e', '#f5edf1', '#49404f') if dark else ('#fbf7f8', '#ffffff', '#29212b', '#dccbd1')
    app.setStyleSheet(f'''
        QWidget {{ background: {bg}; color: {text}; font-family: "Segoe UI"; font-size: 13px; }}
        QLabel#brand {{ font-size: 28px; font-weight: 700; color: #d78fa7; padding: 12px; }}
        QLabel#heading {{ font-size: 24px; font-weight: 600; padding: 8px 0; }}
        QLabel#summary {{ font-size: 17px; padding: 20px; background: {panel}; border-radius: 12px; }}
        QPushButton {{ background: #b66d88; color: white; padding: 10px 15px; border: none; border-radius: 7px; }}
        QPushButton:hover {{ background: #ce829f; }}
        QPushButton:disabled {{ background: #665560; }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QTableWidget {{ background: {panel}; border: 1px solid {border}; border-radius: 6px; padding: 7px; }}
        QListWidget {{ background: {panel}; border: none; border-radius: 9px; }}
        QListWidget::item {{ padding: 13px 8px; }}
        QListWidget::item:selected {{ background: #75485f; color: white; border-radius: 5px; }}
        QHeaderView::section {{ background: {panel}; color: {text}; padding: 7px; border: none; }}
        QCheckBox {{ padding: 5px; }}
    ''')


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Hana AI')
    app.setOrganizationName('HanaAI')
    app.setWindowIcon(icon())
    root = Path(os.environ.get('HANA_DATA_DIR', str(Path.home() / '.hana-ai')))
    root.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / 'desktop.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None, 'Hana AI is running', 'Hana AI is already running. Open it from your system tray.')
        return 0
    if '--smoke-test' in sys.argv:
        window = Window(background=False)
        window.show()
        QTimer.singleShot(1000, app.quit)
    else:
        window = Window()
        window.show()
    apply_theme(app, store.setting('theme', 'Dark'))
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    result = app.exec()
    lock.unlock()
    return result
