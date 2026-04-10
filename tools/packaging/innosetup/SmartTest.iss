[Setup]
AppId={{9E4F9F2A-7A9B-4D4D-9E1A-2C5EF80B0D7A}
AppName=SmartTest
AppVersion=0.1.0
AppPublisher=SmartTest
DefaultDirName={autopf}\SmartTest
DefaultGroupName=SmartTest
OutputBaseFilename=SmartTest-Setup
OutputDir=..\..\..\dist_installer
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\SmartTest.exe
SetupIconFile=..\assets\SmartTest.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if FileExists(CompilerPath + "Languages\\ChineseSimplified.isl")
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\\ChineseSimplified.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\..\..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SmartTest"; Filename: "{app}\SmartTest.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\SmartTest"; Filename: "{app}\SmartTest.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\SmartTest.exe"; Description: "Launch SmartTest"; Flags: nowait postinstall skipifsilent
