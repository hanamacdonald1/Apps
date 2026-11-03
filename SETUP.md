# Set up Hana AI

## 1. Run the dashboard and worker

Install Python 3.11+ and Ollama from their official websites. In PowerShell:

```powershell
ollama pull qwen3:4b
```

Download **Code > Download ZIP** from this repository and extract it. Double-click **Start-Hana-AI.cmd**. It creates a Python environment, installs requirements, starts a worker window and launches the dashboard on 127.0.0.1. Windows may ask you to allow the downloaded launcher to run: only run your own downloaded repository copy.

Alternatively, open PowerShell in the extracted folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

In a second PowerShell window in that folder:

```powershell
.\.venv\Scripts\python.exe worker.py
```

The app can run without Ollama for scans and actions. The chat coordinator needs a model supporting tool calls. If your model cannot do this, use the dashboard buttons or change models. Model quality and speed depend on your computer.

## 2. Add live job sources

- Register at https://developer.adzuna.com/ for an application ID and key. Follow the provider's current terms and quota.
- Enter these in **Settings > Adzuna Australia connection**. They are saved in the OS credential vault.
- Set a location, up to five search phrases and comma-separated ranking terms. Save.
- Optionally paste direct, public HTTPS job RSS or Atom feeds, one per line. Redirects, private addresses and nonstandard ports are rejected. The app does not scrape SEEK or LinkedIn; job alerts from those services can be found through your inbox.
- Open Jobs and click **Scan jobs now**. Each listing retains its source and original link. No configured source means no results, with that limitation recorded in Activity.

## 3. Connect Gmail

Follow Google's [Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python):

1. Create/select a Google Cloud project and enable Gmail API.
2. Configure Google Auth Platform consent settings for your personal app. If in Testing, add your Gmail account as a test user.
3. Create OAuth credentials of type **Desktop app** and download the client JSON.
4. In Hana AI Settings, expand **Connect Gmail** and upload that client JSON. It is used in memory, not written into this repository.
5. Leave send permission off for scanning only, or enable it if you want reviewed cancellation emails sent.
6. Click **Connect Gmail on this computer**, then complete Google's browser sign-in and consent.

Do this on the computer running the app: the Google callback uses that computer's loopback address. Gmail restricted-scope test apps can have limited token lifetimes; reconnect when needed. Personal use does not remove Google's access or verification requirements.

## 4. Connect Outlook / Hotmail

Follow Microsoft's [device flow documentation](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-acquire-token-device-code-flow):

1. Open Microsoft Entra app registrations and register an application supporting organizational accounts **and personal Microsoft accounts** if you use Hotmail/Outlook.com.
2. Under Authentication, enable **Allow public client flows**. This is a public desktop client, so do not create or enter a client secret.
3. Add delegated Microsoft Graph **Mail.Read**, and optionally **Mail.Send** for cancellation emails. Organizational policies may require administrator consent.
4. Copy the application client ID into Hana AI Settings.
5. Choose whether to request sending access. Click **Start Outlook sign-in**.
6. Follow the displayed Microsoft verification URL and user code, sign in, then click **I completed Microsoft sign-in** in the app.

Tokens are stored in your OS credential vault. Changing scopes requires reconnecting. The app supports one Gmail and one Microsoft account at a time.

## 5. Turn on autonomous work

In **Settings > Autonomous schedule**, select the scans and interval, then save. In the sidebar, turn on **Enable agent actions**. Keep `worker.py` running. Background status updates after a successful worker tick. Nothing runs while your computer is off or asleep.

For a cancellation email: review the source, find the service's official support address, create the exact request in **Subscriptions**, then review and approve it in **Actions**. The worker submits that approved email through your chosen connected account. It will not send pending or revoked requests. It cannot cancel every service through an email; some require a portal. Verify the provider's confirmation before treating a subscription as cancelled.

## Privacy and troubleshooting

- Keep Streamlit bound to `127.0.0.1`. This app has no internet-facing login or multi-user isolation.
- OS credential vault errors mean `keyring` has no working backend; Windows Credential Manager normally supplies one. Linux requires a supported unlocked desktop keyring. There is deliberately no plaintext-token fallback.
- Local records live in `~/.hana-ai`. You may override the directory with `HANA_DATA_DIR`. Avoid synced or shared folders for private records.
- Disconnect buttons remove local OAuth credentials. Revoke the app grant in Google/Microsoft account settings if you also want to terminate provider-side access.
- A worker killed while sending may leave the action marked `sending`. Inspect Sent mail before creating a replacement; automatic retries are intentionally blocked to avoid duplicates.
- Pause prevents the next action from starting; a scan or send already in flight may finish.

## Reference APIs

- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Adzuna search](https://developer.adzuna.com/docs/search)
- [Gmail sending](https://developers.google.com/workspace/gmail/api/guides/sending)
- [Microsoft Graph sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
