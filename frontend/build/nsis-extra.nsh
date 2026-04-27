; LuomiNest NSIS Custom Script
; Enhanced installer with Ollama-style UI and advanced features
; Version: 3.0.0
;
; electron-builder provides these defines:
;   PRODUCT_NAME, PRODUCT_FILENAME, APP_FILENAME, APP_PACKAGE_NAME
;   VERSION, COMPANY_NAME, APP_DESCRIPTION, APP_ID, APP_GUID

!macro customInit
  UserInfo::GetAccountType
  Pop $0
  StrCmp $0 "Admin" +3
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${PRODUCT_NAME}"
    Goto +2
    StrCpy $INSTDIR "$PROGRAMFILES64\${PRODUCT_NAME}"
!macroend

!macro customInstall
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayVersion" "${VERSION}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "Publisher" "${COMPANY_NAME}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayIcon" "$INSTDIR\${PRODUCT_NAME}.exe,0"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "InstallLocation" "$INSTDIR"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "URLInfoAbout" "https://github.com/LuminousCX/LuomiNest"
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                     "NoModify" 1
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                     "NoRepair" 1

  WriteRegStr HKCU "Software\Classes\Applications\${PRODUCT_NAME}.exe" \
                  "FriendlyAppName" "${PRODUCT_NAME}"
!macroend

!macro customUnInstall
  DeleteRegKey SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
  DeleteRegValue HKCU "Software\Classes\Applications\${PRODUCT_NAME}.exe" "FriendlyAppName"
  Delete "$SMSTARTUP\${PRODUCT_NAME}.lnk"
!macroend

!macro customUnInit
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\locales"
!macroend

!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_LICENSEPAGE_RADIOBUTTONS
