' Lance la verification du tunnel ORB sans fenetre de console.
Option Explicit

Dim fso, shell, base, script, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

base = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(base, "quick_tunnel.ps1")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & script & """ -Check"

shell.Run cmd, 0, True
