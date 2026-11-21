' StruKit launcher (the Desktop icon runs this): opens the app with no console window.
' A first-time setup goes through strukit.bat instead.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
app = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(app)
args = ""
For Each a In WScript.Arguments
  args = args & " """ & a & """"
Next
ready = fso.FileExists(root & "\runtime\pythonw.exe") And fso.FileExists(root & "\runtime\installed.txt")
If ready Then
  ready = (fso.OpenTextFile(root & "\runtime\installed.txt").ReadAll = fso.OpenTextFile(app & "\downloads.txt").ReadAll)
End If
If WScript.Arguments.Count = 0 And ready Then
  sh.CurrentDirectory = root
  sh.Run """" & root & "\runtime\pythonw.exe"" -m strukit.gui", 0, False
Else
  sh.Run """" & root & "\strukit.bat""" & args, 1, False
End If
