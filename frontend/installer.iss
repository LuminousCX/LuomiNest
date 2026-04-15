#define MyAppName "LuomiNest"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "LuminousCX R&D Team"
#define MyAppExeName "LuomiNest.exe"
#define MyAppId "com.luominest.desktop"
#define MyAppURL "https://github.com/LuminousCX/LuomiNest"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=release\installer
OutputBaseFilename=LuomiNest-Setup-{#MyAppVersion}
SetupIconFile=resources\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
ShowLanguageDialog=yes
UsePreviousLanguage=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.InstallModeTitle=安装模式
chinesesimplified.InstallModeSubtitle=选择为谁安装 {#MyAppName}
chinesesimplified.InstallModeAllUsers=为所有用户安装（推荐）
chinesesimplified.InstallModeAllUsersDesc=将 {#MyAppName} 安装到所有用户可访问的位置，需要管理员权限
chinesesimplified.InstallModeCurrentUser=仅为当前用户安装
chinesesimplified.InstallModeCurrentUserDesc=将 {#MyAppName} 安装到当前用户目录，无需管理员权限
chinesesimplified.LicenseAgreement=许可协议
chinesesimplified.LicenseAgreementDesc=请阅读以下许可协议
english.InstallModeTitle=Install Mode
english.InstallModeSubtitle=Choose for whom to install {#MyAppName}
english.InstallModeAllUsers=Install for all users (Recommended)
english.InstallModeAllUsersDesc=Install {#MyAppName} to a location accessible by all users. Requires administrator privileges.
english.InstallModeCurrentUser=Install for current user only
english.InstallModeCurrentUserDesc=Install {#MyAppName} to the current user directory. No administrator privileges required.

[Code]
var
  InstallModePage: TInputOptionWizardPage;

procedure InitializeWizard;
begin
  InstallModePage := CreateInputOptionPage(
    wpLicense,
    ExpandConstant('{cm:InstallModeTitle}'),
    ExpandConstant('{cm:InstallModeSubtitle}'),
    '',
    True,
    False
  );
  InstallModePage.Add(ExpandConstant('{cm:InstallModeAllUsers}'));
  InstallModePage.Add(ExpandConstant('{cm:InstallModeCurrentUser}'));
  InstallModePage.Values[0] := True;
  InstallModePage.Values[1] := False;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = InstallModePage.ID then
  begin
    WizardForm.DirEdit.Text := ExpandConstant('{autopf}\{#MyAppName}');
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  if CurPageID = InstallModePage.ID then
  begin
    if InstallModePage.Values[0] then
    begin
      WizardForm.DirEdit.Text := ExpandConstant('{commonpf}\{#MyAppName}');
      WizardForm.GroupEdit.Text := ExpandConstant('{commonprograms}\{#MyAppName}');
    end
    else
    begin
      WizardForm.DirEdit.Text := ExpandConstant('{userpf}\{#MyAppName}');
      WizardForm.GroupEdit.Text := ExpandConstant('{userprograms}\{#MyAppName}');
    end;
  end;
end;

function InitializeSetup: Boolean;
begin
  Result := True;
end;

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; Check: not IsAdminInstallMode

[Files]
Source: "release\dist\win-unpacked\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
