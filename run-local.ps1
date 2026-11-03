param(
    [ValidateSet('anomaly','quantum','pqc','security','agent','test')]
    [string]$Project = 'anomaly'
)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Python environment not found. Follow README.md setup first.'
}
$taskPython = (Resolve-Path -LiteralPath $taskPython).Path
$taskOldOqs = $env:OQS_INSTALL_PATH
Push-Location $PSScriptRoot
try {
    $env:OQS_INSTALL_PATH = Join-Path $PSScriptRoot 'runtime/liboqs'
    switch ($Project) {
        'anomaly' { & $taskPython -X utf8 -m anomaly.main }
        'quantum' { & $taskPython -X utf8 -m quantum.main }
        'pqc' { & $taskPython -X utf8 -m pqc.main --iterations 10 }
        'security' { & $taskPython -X utf8 -m security.main --targets 127.0.0.1 --allowlist security/allowlist.txt --ports 80,443 }
        'agent' { & $taskPython -X utf8 -m agent.main --mode demo }
        'test' { & $taskPython -X utf8 -m pytest -q }
    }
    if ($LASTEXITCODE -ne 0) { throw "Project command failed with exit code $LASTEXITCODE" }
} finally {
    $env:OQS_INSTALL_PATH = $taskOldOqs
    Pop-Location
}
