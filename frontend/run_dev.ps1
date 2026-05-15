Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:5173"
} | Out-Null

npm.cmd run dev
