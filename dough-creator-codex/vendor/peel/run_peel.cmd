@echo off
rem Launch the vendored peel MCP server (stdio).
rem
rem Python interpreter resolution:
rem   1. TOAST_PYTHON env var — explicit override (point it at any interpreter
rem      that has the peel deps, e.g. a Toast install's bundled Python).
rem   2. python on PATH — the default. Needs: mcp, httpx, httpx-sse.
rem      (pip install mcp httpx httpx-sse)  If they are missing, peel fails to
rem      start and its tools are simply unavailable — connected-tier discovery
rem      and bakes won't work until the deps are present.
setlocal
set "SCRIPT=%~dp0mcp_server.py"

if defined TOAST_PYTHON (
  "%TOAST_PYTHON%" "%SCRIPT%"
  exit /b %errorlevel%
)

python "%SCRIPT%"
exit /b %errorlevel%
