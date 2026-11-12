$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting AI Advisory Council Backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$backend = Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory "$root\backend" -PassThru

Write-Host "Starting AI Advisory Council Frontend on http://localhost:5173 ..." -ForegroundColor Cyan
$frontend = Start-Process -FilePath "pnpm.cmd" `
    -ArgumentList "dev" `
    -WorkingDirectory "$root\frontend" -PassThru

Write-Host "Backend PID: $($backend.Id) | Frontend PID: $($frontend.Id)" -ForegroundColor Green
Write-Host "Open http://localhost:5173 in your browser. Press Ctrl+C or close windows to stop."
