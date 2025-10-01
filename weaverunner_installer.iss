[Setup]
AppId={{e0f723a9-14e5-4507-bbc0-7016d37c3000}}
AppName=WeaveRunner
AppVersion=1.0
AppPublisher=Ayrlin Renata
AppPublisherURL=https://ayrl.in/
DefaultDirName={autopf}\WeaveRunner
DefaultGroupName=WeaveRunner
AllowNoIcons=yes
OutputBaseFilename=weaverunner-setup
OutputDir=.\dist\installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Components]
Name: "app"; Description: "WeaveRunner Application"; Types: full compact custom; Flags: fixed
Name: "app\gpu"; Description: "GPU-Accelerated Version (NVIDIA CUDA 12.1+)"; Types: custom; Flags: exclusive

[Files]
Source: "dist\gpu\WeaveRunner\*"; DestDir: "{app}"; Components: app\gpu; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\WeaveRunner"; Filename: "{app}\WeaveRunner.exe"
Name: "{autodesktop}\WeaveRunner"; Filename: "{app}\WeaveRunner.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WeaveRunner.exe"; Description: "{cm:LaunchProgram,WeaveRunner}"; Flags: nowait postinstall skipifsilent