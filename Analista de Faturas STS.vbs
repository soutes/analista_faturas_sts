' ==========================================================
' Analista Financeiro - modo aplicativo nativo
' Roda Streamlit silencioso e abre em janela Edge/Chrome
' sem barra de URL, sem abas. Aparência de app desktop.
' ==========================================================

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

' Pasta do projeto = pasta do .vbs
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = projectDir

url  = "http://localhost:8501"
port = "8501"

' --- 1. Sobe o Streamlit em background (sem terminal) ---
streamlitCmd = "python -m streamlit run app.py" _
             & " --server.headless=true" _
             & " --server.port=" & port _
             & " --browser.gatherUsageStats=false"
sh.Run "cmd /c " & streamlitCmd, 0, False

' --- 2. Espera o servidor responder (max 30s) ---
Set http = CreateObject("MSXML2.XMLHTTP")
ready = False
For i = 1 To 60
    WScript.Sleep 500
    On Error Resume Next
    http.Open "GET", url, False
    http.Send
    If Err.Number = 0 And http.Status = 200 Then
        ready = True
        Exit For
    End If
    Err.Clear
    On Error Goto 0
Next

If Not ready Then
    MsgBox "Streamlit não respondeu em 30s. Verifique data/agent.log.", _
           48, "Analista Financeiro"
    WScript.Quit 1
End If

' --- 3. Tenta abrir Edge ou Chrome em modo --app ---
edge1   = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
edge2   = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
chrome1 = "C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome2 = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

userData = projectDir & "\data\.browser_profile"
If Not fso.FolderExists(userData) Then fso.CreateFolder(userData)

appArgs = " --app=" & url _
        & " --start-maximized" _
        & " --user-data-dir=""" & userData & """"

browser = ""
If fso.FileExists(edge1) Then
    browser = edge1
ElseIf fso.FileExists(edge2) Then
    browser = edge2
ElseIf fso.FileExists(chrome1) Then
    browser = chrome1
ElseIf fso.FileExists(chrome2) Then
    browser = chrome2
End If

If browser <> "" Then
    sh.Run """" & browser & """" & appArgs, 1, False
Else
    ' Fallback: abre no navegador padrão (com barra de URL)
    sh.Run url, 1, False
End If

' --- 4. Monitora a janela do browser; mata Streamlit quando fechar ---
pidFile   = projectDir & "\data\.streamlit.pid"
appTitle  = "Analista Financeiro de Faturas"
zeroCount = 0

' Aguarda PID file aparecer (max 10s)
For i = 1 To 20
    If fso.FileExists(pidFile) Then Exit For
    WScript.Sleep 500
Next

' Lê o PID gravado pelo app.py
streamlitPid = ""
If fso.FileExists(pidFile) Then
    Set f = fso.OpenTextFile(pidFile, 1)
    streamlitPid = Trim(f.ReadAll)
    f.Close
End If

' Loop: verifica a cada 3s se a janela ainda existe
tmpFile = projectDir & "\data\.win_check.txt"

Do
    WScript.Sleep 3000

    ' Roda PowerShell oculto (-WindowStyle Hidden) e redireciona saída p/ arquivo
    ' sh.Run com style=0 esconde o cmd; bWaitOnReturn=True espera terminar
    psQuery = "(Get-Process -Name msedge,chrome -EA SilentlyContinue" & _
              " | Where-Object {$_.MainWindowTitle -like '*Analista Financeiro*'}).Count"
    sh.Run "cmd /c powershell -NoProfile -NonInteractive -WindowStyle Hidden" & _
           " -Command """ & psQuery & """ > """ & tmpFile & """", 0, True

    winCount = 0
    If fso.FileExists(tmpFile) Then
        On Error Resume Next
        Set f = fso.OpenTextFile(tmpFile, 1)
        winCount = CInt(Trim(f.ReadAll))
        f.Close
        fso.DeleteFile tmpFile
        On Error GoTo 0
    End If

    If winCount = 0 Then
        zeroCount = zeroCount + 1
        ' 2 verificações consecutivas sem janela = confirmado fechado (~6s)
        If zeroCount >= 2 Then
            If streamlitPid <> "" Then
                sh.Run "taskkill /F /PID " & streamlitPid, 0, True
            End If
            If fso.FileExists(pidFile) Then fso.DeleteFile pidFile
            Exit Do
        End If
    Else
        zeroCount = 0
    End If

    ' Se PID file sumiu, o botão Fechar já tratou o encerramento
    If Not fso.FileExists(pidFile) Then Exit Do
Loop
