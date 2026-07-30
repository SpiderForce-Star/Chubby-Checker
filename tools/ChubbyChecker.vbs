' Silent launcher for Ascent Chubby / Chubby Checker.
' No Command Prompt. Flow: Loading.mp4 -> Twist1960 access gate -> main UI.
' Desktop shortcut should target: wscript.exe //B "…\tools\ChubbyChecker.vbs"
Option Explicit

Dim sh, fso, root, py, gui, logPath, cmd, rc

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
gui = root & "\tools\gui_launcher.py"
logPath = root & "\tools\launch_error.log"

If Not fso.FileExists(gui) Then
  Call Fail("gui_launcher.py not found:" & vbCrLf & gui)
End If

py = ResolvePython(root)
If py = "" Then
  Call Fail("Python not found." & vbCrLf & _
    "Install Python 3.11+ or create a venv at:" & vbCrLf & root & "\.venv")
End If

' Hidden window (0), do not wait (False) — daily use: no console flash
cmd = """" & py & """ """ & gui & """"
sh.CurrentDirectory = root
On Error Resume Next
rc = sh.Run(cmd, 0, False)
If Err.Number <> 0 Then
  Call Fail("Failed to start:" & vbCrLf & cmd & vbCrLf & Err.Description)
End If
On Error GoTo 0
WScript.Quit 0

Function ResolvePython(repoRoot)
  Dim p, pf, pf86, localApp
  ' Prefer venv pythonw (no console). Absolute paths only — no cmd flash.
  p = repoRoot & "\.venv\Scripts\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = repoRoot & "\.venv\Scripts\python.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function

  localApp = sh.ExpandEnvironmentStrings("%LocalAppData%")
  ' Python 3.13+ "Python install manager" layout
  p = localApp & "\Python\bin\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = localApp & "\Programs\Python\Python314\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = localApp & "\Programs\Python\Python313\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = localApp & "\Programs\Python\Python312\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = localApp & "\Programs\Python\Python311\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function

  pf = sh.ExpandEnvironmentStrings("%ProgramFiles%")
  p = pf & "\Python314\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = pf & "\Python312\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function
  p = pf & "\Python311\pythonw.exe"
  If fso.FileExists(p) Then ResolvePython = p: Exit Function

  ' Last resort: PATH (still launched hidden via Run style 0)
  ResolvePython = "pythonw"
End Function

Sub Fail(msg)
  On Error Resume Next
  Dim ts
  Set ts = fso.CreateTextFile(logPath, True)
  ts.WriteLine Now & "  " & msg
  ts.Close
  ' One dialog only on hard failure — never a console window
  MsgBox msg & vbCrLf & vbCrLf & "Details: " & logPath, _
    vbCritical, "Ascent Chubby — launch failed"
  WScript.Quit 1
End Sub
