@echo off
rem Launch the vendored peel MCP server (stdio). Resolution order for the
rem Python interpreter (needs mcp + httpx + httpx-sse installed):
rem   1. TOAST_PYTHON env var (explicit override)
rem   2. Toast/Mojo dev repo embedded Python — main checkout, then worktrees
rem      (extraResources is downloaded per-checkout, so any worktree may have it)
rem   3. python on PATH (last resort; install deps yourself)
setlocal
set "SCRIPT=%~dp0mcp_server.py"
set "REL=src\extraResources\python\win32-x64\python\python.exe"

if defined TOAST_PYTHON (
  "%TOAST_PYTHON%" "%SCRIPT%"
  exit /b %errorlevel%
)

if exist "C:\Code\mojo\%REL%" (
  "C:\Code\mojo\%REL%" "%SCRIPT%"
  exit /b %errorlevel%
)

for /d %%W in ("C:\Code\mojo\.worktrees\*") do (
  if exist "%%W\%REL%" (
    "%%W\%REL%" "%SCRIPT%"
    exit /b %errorlevel%
  )
)

python "%SCRIPT%"
exit /b %errorlevel%
