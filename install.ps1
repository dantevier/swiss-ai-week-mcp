<#
.SYNOPSIS
  One-command setup: install dependencies, save API keys, register the MCP server in your harnesses.

.DESCRIPTION
  1. Runs `uv sync` for this project.
  2. Asks for the Crawlora and OpenAI keys (both optional) and saves them to the git-ignored .env.
  3. Registers the server as "mcp-swiss-info" for Claude Code, Codex and opencode, whichever are installed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
  .\install.ps1 -Yes          # no prompts; keys are taken from $env:CRAWLORA_API_KEY / $env:OPENAI_API_KEY

.EXAMPLE
  .\install.ps1 -Uninstall    # remove the server from every harness
#>
[CmdletBinding()]
param(
    [switch]$Yes,
    [switch]$Uninstall,
    [switch]$NoSync,
    [string]$EnvFile,
    [string]$OpencodeConfig
)

$ErrorActionPreference = 'Stop'
# $PSScriptRoot is empty inside param() defaults in Windows PowerShell 5.1, so defaults are set here.
$Repo = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $EnvFile) { $EnvFile = Join-Path $Repo '.env' }
if (-not $OpencodeConfig) { $OpencodeConfig = Join-Path $HOME '.config\opencode\opencode.json' }
$Name = 'mcp-swiss-info'
# --directory makes the server work from any project; the server then finds this repo's .env.
$Launch = @('uv', 'run', '--directory', $Repo, 'python', '-m', 'mcp_boilerplate.main')
$Keys = [ordered]@{
    CRAWLORA_API_KEY = 'Crawlora key (fetches the official pages)'
    OPENAI_API_KEY   = 'OpenAI key (semantic search embeddings)'
}
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Failures = 0

function Write-Step($text) { Write-Host "`n$text" -ForegroundColor Cyan }

function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    # Capture output without letting stderr text turn into a terminating error (Windows PowerShell 5.1).
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $text = (& $Exe @Arguments 2>&1 | ForEach-Object { "$_" }) -join "`n"
        return [pscustomobject]@{ Code = $LASTEXITCODE; Output = $text.Trim() }
    }
    finally { $ErrorActionPreference = $previous }
}

function Read-EnvFile {
    $values = @{}
    if (Test-Path $EnvFile) {
        foreach ($line in [IO.File]::ReadAllLines($EnvFile)) {
            if ($line.TrimStart().StartsWith('#')) { continue }
            $i = $line.IndexOf('=')
            if ($i -gt 0) { $values[$line.Substring(0, $i).Trim()] = $line.Substring($i + 1).Trim() }
        }
    }
    return $values
}

function Save-EnvKeys([hashtable]$Updates) {
    foreach ($key in $Updates.Keys) {
        # Same rule as the dashboard: no spaces, quotes, # or backslashes, so a value cannot inject lines.
        if ($Updates[$key] -notmatch '^[^\s"''#\\]+$') {
            throw "$key must not contain spaces, quotes, # or backslashes"
        }
    }
    $lines = New-Object System.Collections.Generic.List[string]
    if (Test-Path $EnvFile) { $lines.AddRange([string[]][IO.File]::ReadAllLines($EnvFile)) }
    $pending = @{} + $Updates
    for ($n = 0; $n -lt $lines.Count; $n++) {
        $line = $lines[$n]
        $i = $line.IndexOf('=')
        if ($i -gt 0 -and -not $line.TrimStart().StartsWith('#')) {
            $existing = $line.Substring(0, $i).Trim()
            if ($pending.ContainsKey($existing)) { $lines[$n] = "$existing=$($pending[$existing])"; $pending.Remove($existing) }
        }
    }
    foreach ($key in $pending.Keys) { $lines.Add("$key=$($pending[$key])") }
    [IO.File]::WriteAllText($EnvFile, (($lines -join "`n") + "`n"), $Utf8)
}

function Read-Secret([string]$Prompt) {
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Save-Keys {
    $current = Read-EnvFile
    $updates = @{}
    foreach ($key in $Keys.Keys) {
        if ($current[$key]) { Write-Host "  ${key}: already set in .env"; continue }
        $value = [Environment]::GetEnvironmentVariable($key)
        if (-not $value -and -not $Yes) { $value = Read-Secret "  $($Keys[$key]) [Enter to skip]" }
        if ($value) { $updates[$key] = $value }
        else { Write-Host "  ${key}: skipped (search falls back to keywords; refresh is disabled)" }
    }
    if ($updates.Count -gt 0) {
        Save-EnvKeys $updates
        Write-Host "  saved $($updates.Keys -join ', ') to .env (git-ignored)"
    }
}

function Get-OpencodeSnippet {
    $entry = [ordered]@{ type = 'local'; command = @($Launch); enabled = $true }
    return (ConvertTo-Json -InputObject ([ordered]@{ mcp = [ordered]@{ $Name = $entry } }) -Depth 10)
}

function Update-Opencode([bool]$Remove) {
    $config = $null
    if (Test-Path $OpencodeConfig) {
        try { $config = [IO.File]::ReadAllText($OpencodeConfig).TrimStart([char]0xFEFF) | ConvertFrom-Json }
        catch { throw "$OpencodeConfig is not plain JSON; merge this in by hand:`n$(Get-OpencodeSnippet)" }
    }
    if ($null -eq $config) {
        if ($Remove) { return "nothing to remove" }
        $config = [pscustomobject]@{ '$schema' = 'https://opencode.ai/config.json' }
    }
    if (-not $config.PSObject.Properties['mcp']) {
        if ($Remove) { return "nothing to remove" }
        $config | Add-Member -NotePropertyName mcp -NotePropertyValue ([pscustomobject]@{})
    }
    if ($Remove) {
        if (-not $config.mcp.PSObject.Properties[$Name]) { return "nothing to remove" }
        $config.mcp.PSObject.Properties.Remove($Name)
    }
    else {
        $entry = [pscustomobject]@{ type = 'local'; command = @($Launch); enabled = $true }
        $config.mcp | Add-Member -NotePropertyName $Name -NotePropertyValue $entry -Force
    }
    New-Item -ItemType Directory -Force (Split-Path $OpencodeConfig) | Out-Null
    [IO.File]::WriteAllText($OpencodeConfig, ((ConvertTo-Json -InputObject $config -Depth 20) + "`n"), $Utf8)
    return "$(if ($Remove) { 'removed from' } else { 'updated' }) $OpencodeConfig"
}

function Register-Cli([string]$Cli, [string[]]$AddArgs, [string[]]$RemoveArgs, [bool]$Remove) {
    $exe = (Get-Command $Cli -ErrorAction Stop).Source
    # Adding twice is an error in these CLIs, so drop any earlier entry first (this also makes reruns safe).
    $null = Invoke-Native $exe $RemoveArgs
    if ($Remove) { return 'removed' }
    $result = Invoke-Native $exe $AddArgs
    if ($result.Code -ne 0) { throw $(if ($result.Output) { $result.Output } else { "$Cli exited with $($result.Code)" }) }
    return $(if ($result.Output) { $result.Output } else { 'registered' })
}

$Harnesses = @(
    @{ Id = 'claude'; Label = 'Claude Code'
       Add = @('mcp', 'add', '--scope', 'user', $Name, '--') + $Launch
       Remove = @('mcp', 'remove', '--scope', 'user', $Name) },
    @{ Id = 'codex'; Label = 'Codex'
       Add = @('mcp', 'add', $Name, '--') + $Launch
       Remove = @('mcp', 'remove', $Name) },
    @{ Id = 'opencode'; Label = 'opencode' }
)

if (-not $Uninstall) {
    Write-Step '1/3 Installing dependencies'
    if ($NoSync) { Write-Host '  skipped (-NoSync)' }
    elseif (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv is not installed. Install it first (https://docs.astral.sh/uv/getting-started/installation/), then rerun."
    }
    else {
        Push-Location $Repo
        try { & uv sync --all-extras; if ($LASTEXITCODE -ne 0) { throw "uv sync failed" } }
        finally { Pop-Location }
    }
    Write-Step '2/3 API keys'
    Save-Keys
}

Write-Step $(if ($Uninstall) { 'Removing the MCP server' } else { '3/3 Registering the MCP server' })
# opencode has no CLI we can script, so its config is only touched if opencode or its config exists.
$found = @($Harnesses | Where-Object { (Get-Command $_.Id -ErrorAction SilentlyContinue) -or ($_.Id -eq 'opencode' -and (Test-Path $OpencodeConfig)) })
if ($found.Count -eq 0) {
    Write-Host '  No claude, codex or opencode found on PATH.'
    Write-Host "  Run manually, e.g.: claude mcp add --scope user $Name -- $($Launch -join ' ')"
}
foreach ($h in $found) {
    if (-not $Yes) {
        $verb = if ($Uninstall) { 'Remove from' } else { 'Register in' }
        if ((Read-Host "  $verb $($h.Label)? [Y/n]") -match '^(n|no)$') { continue }
    }
    try {
        $message = if ($h.Id -eq 'opencode') { Update-Opencode $Uninstall }
                   else { Register-Cli $h.Id $(if ($Uninstall) { $h.Remove } else { $h.Add }) $h.Remove $Uninstall }
        Write-Host "  $($h.Label): $message"
    }
    catch {
        $Failures++
        Write-Host "  $($h.Label): FAILED - $($_.Exception.Message)" -ForegroundColor Red
    }
}

if (-not $Uninstall) { Write-Host "`nDone. Restart your harness, then ask: `"How fresh is your data?`"" }
exit $(if ($Failures -gt 0) { 1 } else { 0 })
