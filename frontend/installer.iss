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
chinesesimplified.InstallModeAllUsersNoAdmin=为所有用户安装需要管理员权限
chinesesimplified.InstallModeAllUsersNoAdminDesc=您当前没有管理员权限。选择"为所有用户安装"将请求提升权限。
chinesesimplified.LicenseAgreement=许可协议
chinesesimplified.LicenseAgreementDesc=请阅读以下许可协议
english.InstallModeTitle=Install Mode
english.InstallModeSubtitle=Choose for whom to install {#MyAppName}
english.InstallModeAllUsers=Install for all users (Recommended)
english.InstallModeAllUsersDesc=Install {#MyAppName} to a location accessible by all users. Requires administrator privileges.
english.InstallModeCurrentUser=Install for current user only
english.InstallModeCurrentUserDesc=Install {#MyAppName} to the current user directory. No administrator privileges required.
english.InstallModeAllUsersNoAdmin=Install for all users requires administrator privileges
english.InstallModeAllUsersNoAdminDesc=You do not currently have administrator privileges. Selecting "Install for all users" will request elevation.
english.LicenseAgreement=License Agreement
english.LicenseAgreementDesc=Please read the following license agreement

[Code]
var
  InstallModePage: TInputOptionWizardPage;
  IsAdmin: Boolean;

function IsAdminUser: Boolean;
begin
  Result := IsAdminLoggedOn or IsPowerUserLoggedOn;
end;

procedure InitializeWizard;
begin
  IsAdmin := IsAdminUser;

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

  if IsAdmin then
  begin
    InstallModePage.Values[0] := True;
    InstallModePage.Values[1] := False;
  end
  else
  begin
    InstallModePage.Values[0] := False;
    InstallModePage.Values[1] := True;
  end;
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
      if not IsAdmin then
      begin
        if MsgBox(ExpandConstant('{cm:InstallModeAllUsersNoAdminDesc}'), mbConfirmation, MB_YESNO) = IDNO then
        begin
          Result := False;
          Exit;
        end;
      end;

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
var
  OldUninstallString: String;
begin
  Result := True;

  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1',
    'UninstallString', OldUninstallString) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1',
    'UninstallString', OldUninstallString) then
  begin
    if MsgBox('{#MyAppName} is already installed. Do you want to uninstall the previous version first?',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      OldUninstallString := RemoveQuotes(OldUninstallString);
      Exec(OldUninstallString, '/SILENT /NORESTART', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if InstallModePage.Values[0] then
    begin
      RegWriteStringValue(HKLM, 'SOFTWARE\{#MyAppName}', 'InstallMode', 'machine');
      RegWriteStringValue(HKLM, 'SOFTWARE\{#MyAppName}', 'InstallPath', ExpandConstant('{app}'));
    end
    else
    begin
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'InstallMode', 'user');
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'InstallPath', ExpandConstant('{app}'));
    end;
  end;
end;

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; Check: not IsAdminInstallMode

[Files]
Source: "release\dist\win-unpacked\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"
Name: "{group}\License"; Filename: "{app}\LICENSE"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
