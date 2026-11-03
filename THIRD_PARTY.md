# Third-party components

Hana AI uses third-party packages under their respective licences. The desktop onedir bundle preserves Qt as shared libraries rather than statically linking it. Keep the runtime folder with the executable; replace compatible libraries there when exercising rights under their licences.

- Qt / PySide6: LGPLv3/GPL/commercial options. This application uses the open-source Qt Widgets components. Licence text: https://www.gnu.org/licenses/lgpl-3.0.html . Qt source and notices: https://code.qt.io/cgit/ and https://doc.qt.io/qt-6/licenses-used-in-qt.html . Python bindings source: https://code.qt.io/cgit/pyside/pyside-setup.git/ . No proprietary Qt modules are required.
- Python: https://docs.python.org/3/license.html
- Requests: https://github.com/psf/requests/blob/main/LICENSE
- Google API Python Client: https://github.com/googleapis/google-api-python-client/blob/main/LICENSE
- Google Auth OAuthlib: https://github.com/googleapis/google-auth-library-python-oauthlib/blob/main/LICENSE
- MSAL Python: https://github.com/AzureAD/microsoft-authentication-library-for-python/blob/dev/LICENSE
- keyring: https://github.com/jaraco/keyring/blob/main/LICENSE
- pypdf: https://github.com/py-pdf/pypdf/blob/main/LICENSE
- PyInstaller exception permits redistribution of bundled applications: https://pyinstaller.org/en/stable/license.html

The packaging process collects installed package licence files where supplied. Remotive data retains source attribution and original URLs; source rules: https://github.com/remotive-com/remote-jobs-api . No third-party account access, API quota or model weights are bundled as credentials.
