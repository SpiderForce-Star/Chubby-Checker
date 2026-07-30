' Silent launcher: no console window. Double-click or use as Desktop shortcut target.
Option Explicit
Dim sh, fso, root, py, gui, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
gui = root & "\tools\gui_launcher.py"

If fso.FileExists(root & "\.venv\Scripts\pythonw.exe") Then
  py = root & "\.venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(root & "\.venv\Scripts\python.exe") Then
  py = root & "\.venv\Scripts\python.exe"
Else
  py = "pythonw"
End If

cmd = """" & py & """ """ & gui & """"
sh.CurrentDirectory = root
sh.Run cmd, 0, False
