param([string]$Mode = "")

$dir = $PSScriptRoot

$modes = @{
    "servitor" = "prompt_servitor.txt"
    "tafe"     = "prompt_tafe_ict_analysis.txt"
    "lyrical"  = "prompt_lyrical.txt"
}

if ($Mode -eq "" -or $Mode -eq "list") {
    Write-Host "Available modes:"
    Write-Host "  servitor  -- SERVITOR war-engine persona (requires prompt_servitor.txt)"
    Write-Host "  tafe      -- TAFE ICT Analysis tutor (requires prompt_tafe_ict_analysis.txt)"
    Write-Host "  lyrical   -- Lyrical Forge, pure image generation (requires prompt_lyrical.txt)"
    Write-Host ""
    Write-Host "First-time setup:"
    Write-Host "  Copy-Item system_prompt.txt prompt_servitor.txt"
    Write-Host "  Copy-Item prompt_lyrical.example.txt prompt_lyrical.txt"
    exit
}

if (-not $modes.ContainsKey($Mode)) {
    Write-Host "[ERR] Unknown mode: $Mode"
    exit 1
}

$src = Join-Path $dir $modes[$Mode]
$dst = Join-Path $dir "system_prompt.txt"

if (-not (Test-Path $src)) {
    Write-Host "[ERR] $($modes[$Mode]) not found."
    if ($Mode -eq "servitor") { Write-Host "      Run: Copy-Item system_prompt.txt prompt_servitor.txt" }
    if ($Mode -eq "lyrical")  { Write-Host "      Run: Copy-Item prompt_lyrical.example.txt prompt_lyrical.txt" }
    exit 1
}

Copy-Item $src $dst -Force
Write-Host "[OK] Switched to $Mode mode. Hot-reload active."
