!macro customInit
  ; LuomiNest NSIS custom initialization
  ; Check if app is running before install
  nsExec::ExecToLog 'tasklist /FI "IMAGENAME eq LuomiNest.exe" /NH'
  Pop $0
  ${If} $0 == "0"
    MessageBox MB_OKCANCEL|MB_ICONINFORMATION "LuomiNest is running. It will be closed before installation." IDOK closeApp IDCANCEL abortInstall
    closeApp:
      nsExec::ExecToLog 'taskkill /F /IM LuomiNest.exe'
      Goto done
    abortInstall:
      Abort
    done:
  ${EndIf}
!macroend

!macro customInstallMode
  ; Use current user install mode by default
  StrCpy $isForceCurrentInstall "1"
!macroend
