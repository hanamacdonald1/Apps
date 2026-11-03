#define MyAppName "Hana AI"
#define MyAppVersion "0.2.0"
[Setup]
AppId={{83DF7F2E-87FC-4C21-9E38-179A564903D9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\HanaAI
DefaultGroupName=Hana AI
PrivilegesRequired=lowest
OutputDir=..\installer-output
OutputBaseFilename=HanaAI-Setup
SetupIconFile=HanaAI.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\HanaAI.exe
CloseApplications=yes
[Files]
Source: "..\dist\HanaAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Hana AI"; Filename: "{app}\HanaAI.exe"
Name: "{autodesktop}\Hana AI"; Filename: "{app}\HanaAI.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\HanaAI.exe"; Description: "Open Hana AI"; Flags: nowait postinstall skipifsilent
