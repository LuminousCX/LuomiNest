#define MyAppName "LuomiNest"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "LuminousCX R&D Team"
#define MyAppExeName "LuomiNest.exe"
#define MyAppId "com.luominest.desktop"
#define MyAppURL "https://github.com/LuminousCX/LuomiNest"
#define MyAppDescription "辰汐分布式AI伴侣平台"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
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
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
ShowLanguageDialog=no
UsePreviousLanguage=no
MinVersion=6.1sp1
InternalCompressLevel=ultra
LZMAUseSeparateProcess=yes
LZMABlockSize=8192
LZMANumFastBytes=256
LZMADictionarySize=196608

; Ollama-style UI settings
WizardImageFile=
WizardSmallImageFile=
WindowVisible=yes
WindowResizable=no
WindowShowCaption=yes
WindowStartMaximized=no
BackColor=$FFFFFF
BackColor2=$F5F5F5
BackColorDirection=gdVertical
FlatComponentsList=True
ShowComponentSizes=False
ShowTasksTreeLines=False
DisableWelcomePage=False
DisableDirPage=False
DisableProgramGroupPage=False
AlwaysShowDirOnReadyPage=True
AppendDefaultGroupName=False
CreateAppDir=True

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
; Chinese Simplified
chinesesimplified.WelcomeTitle=欢迎使用 {#MyAppName}
chinesesimplified.WelcomeSubTitle=准备安装 {#MyAppName} {#MyAppVersion} 到您的电脑
chinesesimplified.WelcomeDesc1=本向导将引导您完成 {#MyAppName} 的安装过程。
chinesesimplified.WelcomeDesc2=建议您在继续之前关闭所有其他应用程序。
chinesesimplified.WelcomeClickInstall=点击"安装"继续。
chinesesimplified.InstallModeTitle=安装模式
chinesesimplified.InstallModeSubtitle=选择为谁安装 {#MyAppName}
chinesesimplified.InstallModeAllUsers=为所有用户安装（推荐）
chinesesimplified.InstallModeAllUsersDesc=将 {#MyAppName} 安装到所有用户可访问的位置，需要管理员权限
chinesesimplified.InstallModeCurrentUser=仅为当前用户安装
chinesesimplified.InstallModeCurrentUserDesc=将 {#MyAppName} 安装到当前用户目录，无需管理员权限
chinesesimplified.ShortcutsTitle=创建快捷方式
chinesesimplified.ShortcutsSubtitle=选择要创建的快捷方式
chinesesimplified.DesktopShortcut=创建桌面快捷方式
chinesesimplified.DesktopShortcutDesc=在桌面上创建 {#MyAppName} 快捷方式
chinesesimplified.StartMenuShortcut=添加到开始菜单
chinesesimplified.StartMenuShortcutDesc=在Windows开始菜单中创建程序组
chinesesimplified.AutoLaunchShortcut=开机自动启动
chinesesimplified.AutoLaunchShortcutDesc=登录时自动启动 {#MyAppName}
chinesesimplified.LicenseAgreement=许可协议
chinesesimplified.LicenseAgreementDesc=请阅读以下许可协议
chinesesimplified.InstallingTitle=正在安装
chinesesimplified.InstallingSubtitle=请稍候，正在将 {#MyAppName} 安装到您的电脑...
chinesesimplified.FinishedTitle=安装完成
chinesesimplified.FinishedSubTitle={#MyAppName} 已成功安装到您的电脑
chinesesimplified.FinishedRunLabel=启动 {#MyAppName}
chinesesimplified.FinishedLabel=点击"完成"关闭此向导。
chinesesimplified.AlreadyInstalledMsg={#MyAppName} 已经安装在您的电脑上。%n%n是否要先卸载之前的版本？

; English
english.WelcomeTitle=Welcome to {#MyAppName}
english.WelcomeSubTitle=Preparing to install {#MyAppName} {#MyAppVersion} on your computer
english.WelcomeDesc1=This wizard will guide you through the installation of {#MyAppName}.
english.WelcomeDesc2=It is recommended that you close all other applications before continuing.
english.WelcomeClickInstall=Click Install to continue.
english.InstallModeTitle=Installation Mode
english.InstallModeSubtitle=Choose for whom to install {#MyAppName}
english.InstallModeAllUsers=Install for all users (Recommended)
english.InstallModeAllUsersDesc=Install {#MyAppName} to a location accessible by all users. Requires administrator privileges.
english.InstallModeCurrentUser=Install for current user only
english.InstallModeCurrentUserDesc=Install {#MyAppName} to the current user directory. No administrator privileges required.
english.ShortcutsTitle=Shortcuts
english.ShortcutsSubtitle=Choose which shortcuts to create
english.DesktopShortcut=Create desktop shortcut
english.DesktopShortcutDesc=Create a shortcut to {#MyAppName} on your desktop
english.StartMenuShortcut=Add to Start Menu
english.StartMenuShortcutDesc=Create program group in Windows Start Menu
english.AutoLaunchShortcut=Launch at startup
english.AutoLaunchShortcutDesc=Automatically start {#MyAppName} when you log in
english.LicenseAgreement=License Agreement
english.LicenseAgreementDesc=Please read the following license agreement
english.InstallTitle=Installing
english.InstallSubtitle=Please wait while Setup installs {#MyAppName} on your computer.
english.FinishedTitle=Installation Complete
english.FinishedSubTitle={#MyAppName} has been successfully installed on your computer.
english.FinishedRunLabel=Launch {#MyAppName}
english.FinishedLabel=Click Finish to close this wizard.
english.AlreadyInstalledMsg={#MyAppName} is already installed on your computer.%n%nDo you want to uninstall the previous version first?

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:ShortcutsTitle}"; Flags: unchecked
Name: "startmenu"; Description: "{cm:StartMenuShortcut}"; GroupDescription: "{cm:ShortcutsTitle}"; Flags: checkedonce
Name: "autolaunch"; Description: "{cm:AutoLaunchShortcut}"; GroupDescription: "{cm:ShortcutsTitle}"; Flags: unchecked

[Files]
Source: "release\dist\win-unpacked\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenu
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"; Tasks: startmenu
Name: "{group}\License"; Filename: "{app}\LICENSE"; Tasks: startmenu
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; Tasks: startmenu
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autolaunch

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:FinishedRunLabel}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  InstallModePage: TInputOptionWizardPage;
  ShortcutsPage: TWizardPage;
  DesktopCheck, StartMenuCheck, AutoLaunchCheck: TCheckBox;
  IsAdmin: Boolean;

function IsAdminUser: Boolean;
begin
  Result := IsAdminLoggedOn or IsPowerUserLoggedOn;
end;

procedure InitializeWizard;
begin
  IsAdmin := IsAdminUser;

  WizardForm.Position := poScreenCenter;
  WizardForm.ClientWidth := ScaleX(700);
  WizardForm.ClientHeight := ScaleY(500);
  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.Font.Size := 9;
  WizardForm.Color := TColor($FFFFFF);
  WizardForm.OuterNotebook.Color := TColor($FFFFFF);
  WizardForm.InnerNotebook.Color := TColor($FFFFFF);

  ; Customize welcome page labels
  WizardForm.WelcomeLabel1.Font.Size := 16;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel1.Font.Color := TColor($333333);
  WizardForm.WelcomeLabel1.Top := ScaleY(50);

  WizardForm.WelcomeLabel2.Font.Size := 10;
  WizardForm.WelcomeLabel2.Font.Color := TColor($666666);
  WizardForm.WelcomeLabel2.WordWrap := True;
  WizardForm.WelcomeLabel2.Top := ScaleY(100);

  ; Create install mode page
  InstallModePage := CreateInputOptionPage(
    wpLicense,
    ExpandConstant('{cm:InstallModeTitle}'),
    ExpandConstant('{cm:InstallModeSubtitle}'),
    '',
    True,
    False
  );
  InstallModePage.Add(ExpandConstant('{cm:InstallModeAllUsers}') + #13#10 + ExpandConstant('{cm:InstallModeAllUsersDesc}'));
  InstallModePage.Add(ExpandConstant('{cm:InstallModeCurrentUser}') + #13#10 + ExpandConstant('{cm:InstallModeCurrentUserDesc}'));

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

  ; Create shortcuts page
  ShortcutsPage := CreateCustomPage(
    InstallModePage.ID,
    ExpandConstant('{cm:ShortcutsTitle}'),
    ExpandConstant('{cm:ShortcutsSubtitle}')
  );

  DesktopCheck := TCheckBox.Create(ShortcutsPage);
  DesktopCheck.Parent := ShortcutsPage.Surface;
  DesktopCheck.Caption := ExpandConstant('{cm:DesktopShortcut}');
  DesktopCheck.Left := ScaleX(20);
  DesktopCheck.Top := ScaleY(30);
  DesktopCheck.Width := ShortcutsPage.SurfaceWidth - ScaleX(40);
  DesktopCheck.Height := ScaleY(24);
  DesktopCheck.Checked := True;

  StartMenuCheck := TCheckBox.Create(ShortcutsPage);
  StartMenuCheck.Parent := ShortcutsPage.Surface;
  StartMenuCheck.Caption := ExpandConstant('{cm:StartMenuShortcut}');
  StartMenuCheck.Left := ScaleX(20);
  StartMenuCheck.Top := ScaleY(65);
  StartMenuCheck.Width := ShortcutsPage.SurfaceWidth - ScaleX(40);
  StartMenuCheck.Height := ScaleY(24);
  StartMenuCheck.Checked := True;

  AutoLaunchCheck := TCheckBox.Create(ShortcutsPage);
  AutoLaunchCheck.Parent := ShortcutsPage.Surface;
  AutoLaunchCheck.Caption := ExpandConstant('{cm:AutoLaunchShortcut}');
  AutoLaunchCheck.Left := ScaleX(20);
  AutoLaunchCheck.Top := ScaleY(100);
  AutoLaunchCheck.Width := ShortcutsPage.SurfaceWidth - ScaleX(40);
  AutoLaunchCheck.Height := ScaleY(24);
  AutoLaunchCheck.Checked := False;

  ; Style the main buttons
  WizardForm.NextButton.Font.Style := [fsBold];
  WizardForm.BackButton.Font.Style := [];
  WizardForm.CancelButton.Font.Style := [];

  ; Set button colors and styles
  WizardForm.NextButton.ParentColor := False;
  WizardForm.NextButton.Color := TColor($0078D4);
  WizardForm.NextButton.Font.Color := clWhite;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  if PageID = wpSelectTasks then
    Result := True
  else if PageID = wpSelectProgramGroup then
    Result := True
  else
    Result := False;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpInstalling then
  begin
    WizardForm.PageNameLabel.Caption := ExpandConstant('{cm:InstallingTitle}');
    WizardForm.PageDescriptionLabel.Caption := ExpandConstant('{cm:InstallingSubtitle}');
    WizardForm.FileNameLabel.Font.Color := TColor($666666);
    WizardForm.ProgressGauge.ForeColor := $0078D4;
    WizardForm.ProgressGauge.BackColor := $E5E5E5;
  end
  else if CurPageID = wpFinished then
  begin
    WizardForm.PageNameLabel.Caption := ExpandConstant('{cm:FinishedTitle}');
    WizardForm.PageDescriptionLabel.Caption := ExpandConstant('{cm:FinishedSubTitle}');
    WizardForm.RunLabel.Font.Color := TColor($0078D4);
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
  end
  else if CurPageID = ShortcutsPage.ID then
  begin
    if DesktopCheck.Checked then
      WizardSelectTasks('desktopicon')
    else
      WizardSelectTasks('!desktopicon');
    if StartMenuCheck.Checked then
      WizardSelectTasks('startmenu')
    else
      WizardSelectTasks('!startmenu');
    if AutoLaunchCheck.Checked then
      WizardSelectTasks('autolaunch')
    else
      WizardSelectTasks('!autolaunch');
  end;
end;

function InitializeSetup: Boolean;
var
  OldUninstallString: String;
  ResultCode: Integer;
begin
  Result := True;

  ; Check for existing installation
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1',
    'UninstallString', OldUninstallString) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1',
    'UninstallString', OldUninstallString) then
  begin
    if MsgBox(CustomMessage('AlreadyInstalledMsg'), mbConfirmation, MB_YESNO) = IDYES then
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
      RegWriteStringValue(HKLM, 'SOFTWARE\{#MyAppName}', 'DesktopShortcut', BoolToStr(DesktopCheck.Checked, True));
      RegWriteStringValue(HKLM, 'SOFTWARE\{#MyAppName}', 'StartMenuShortcut', BoolToStr(StartMenuCheck.Checked, True));
      RegWriteStringValue(HKLM, 'SOFTWARE\{#MyAppName}', 'AutoLaunch', BoolToStr(AutoLaunchCheck.Checked, True));
    end
    else
    begin
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'InstallMode', 'user');
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'InstallPath', ExpandConstant('{app}'));
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'DesktopShortcut', BoolToStr(DesktopCheck.Checked, True));
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'StartMenuShortcut', BoolToStr(StartMenuCheck.Checked, True));
      RegWriteStringValue(HKCU, 'SOFTWARE\{#MyAppName}', 'AutoLaunch', BoolToStr(AutoLaunchCheck.Checked, True));
    end;
  end;
end;

procedure DeInitializeSetup();
begin
end;
