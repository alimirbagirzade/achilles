Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File """ & "C:\Users\sevinc\Development\achilles\scripts\start-server.ps1" & """", 0, False
Set sh = Nothing
