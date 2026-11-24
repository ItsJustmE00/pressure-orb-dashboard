' Lance le watchdog ORB sans fenetre de console.
Option Explicit

Dim fso, shell, base, script, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

base = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(base, "watchdog_orb.ps1")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & script & """ -Once"

shell.Run cmd, 0, True
