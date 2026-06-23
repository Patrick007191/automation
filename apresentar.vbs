' Abre o demo.html no navegador padrao do Windows
' Este script funciona em QUALQUER PC sem precisar de associacao .html

Dim shell, fso, pasta, arquivo
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Pega a pasta onde este .vbs esta
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
arquivo = pasta & "\demo.html"

' Verifica se o arquivo existe
If fso.FileExists(arquivo) Then
    ' Abre no navegador padrao
    shell.Run "rundll32.exe url.dll,FileProtocolHandler " & arquivo, 1, False
Else
    MsgBox "Arquivo nao encontrado: " & arquivo, vbCritical, "Erro"
End If

Set shell = Nothing
Set fso = Nothing