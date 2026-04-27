; LuomiNest NSIS Custom Script
; Enhanced installer with Ollama-style UI and advanced features
; Version: 2.0.0

!macro customInit
  ; Set default installation directory based on user privileges
  UserInfo::GetAccountType
  Pop $0
  StrCmp $0 "Admin" +3
    ; Non-admin user - use user profile
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\LuomiNest"
    Goto +2
    ; Admin user - use program files
    StrCpy $INSTDIR "$PROGRAMFILES64\LuomiNest"

  ; Set application metadata
  !define /redef APP_NAME "LuomiNest"
  !define /redef APP_VERSION "0.3.0"
  !define /redef APP_PUBLISHER "LuminousCX R&D Team"
  !define /redef APP_DESCRIPTION "辰汐分布式AI伴侣平台"
!macroend

!macro customInstall
  ; Create additional registry entries for better integration
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                   "DisplayName" "${APP_NAME}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                   "DisplayVersion" "${APP_VERSION}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                   "Publisher" "${APP_PUBLISHER}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                   "DisplayIcon" "$INSTDIR\LuomiNest.exe,0"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                   "InstallLocation" "$INSTDIR"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                   "URLInfoAbout" "https://github.com/LuminousCX/LuomiNest"
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                     "NoModify" 1
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                     "NoRepair" 1

  ; Register app in Windows Apps (for Windows 10/11)
  WriteRegStr HKCU "Software\Classes\Applications\LuomiNest.exe" \
                  "FriendlyAppName" "${APP_NAME}"

  ; Create file associations if needed (optional)
  ; WriteRegStr HKCR ".luominest" "" "LuomiNest.File"
  ; WriteRegStr HKCR "LuomiNest.File" "" "LuomiNest Project File"
  ; WriteRegStr HKCR "LuomiNest\File\DefaultIcon" "" "$INSTDIR\LuomiNest.exe,0"
  ; WriteRegStr HKCR "LuomiNest.File\shell\open\command" "" '"$INSTDIR\LuomiNest.exe" "%1"'
!macroend

!macro customInstallDir
  ; Custom installation directory page with Ollama-style layout
  nsDialogs::Create 1018
  Pop $0

  ${NSD_CreateLabel} 0 0 100% 24u "Choose the install location:"
  Pop $0

  ${NSD_CreateDirRequest} 0 35u 100% 14u $INSTDIR
  Pop $INSTDIR_TXT

  ${NSD_CreateBrowseButton} 100% 34u 60u 14u "Browse..."
  Pop $BROWSE_BTN

  ${NSD_OnClick} $BROWSE_BTN OnBrowseClicked

  nsDialogs::Show
!macroend

!macro OnBrowseClicked
  ; Handle browse button click
  Push $0
  nsDialogs::SelectFolderDialog "Select Installation Directory" $INSTDIR
  Pop $0
  StrCmp $0 error +2
    StrCpy $INSTDIR $0
    SendMessage $HWND_PARENT ${WM_SETTEXT} 0 "STR:$INSTDIR"
  Pop $0
!macroend

!macro customUnInstall
  ; Clean up registry entries
  DeleteRegKey SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegValue HKCU "Software\Classes\Applications\LuomiNest.exe" "FriendlyAppName"

  ; Remove file associations if they were created
  ; DeleteRegKey HKCR ".luominest"
  ; DeleteRegKey HKCR "LuomiNest.File"

  ; Remove startup shortcut if it exists
  Delete "$SMSTARTUP\LuomiNest.lnk"
!macroend

!macro customUnInit
  ; Cleanup after uninstallation
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\locales"
!macroend

; Helper macros for UI customization
!define MUI_ICON "resources/icon.ico"
!define MUI_UNICON "resources/icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "resources/icon.ico"
!define MUI_HEADERIMAGE_RIGHT
!define MUI_WELCOMEFINISHPAGE_BITMAP ""

; Modern UI settings
!define MUI_UI "nsisResources.exe"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_LICENSEPAGE_RADIOBUTTONS
