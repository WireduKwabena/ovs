<#
  Export OVS user manual to PDF/DOCX/HTML using Pandoc.

  Examples:
    powershell -ExecutionPolicy Bypass -File docs/scripts/export_user_manual.ps1
    powershell -ExecutionPolicy Bypass -File docs/scripts/export_user_manual.ps1 -Formats docx,html
    powershell -ExecutionPolicy Bypass -File docs/scripts/export_user_manual.ps1 -OutputDir docs/exports -Title "OVS User Manual"
#>

[CmdletBinding()]
param(
    [string]$InputPath = "docs/USER_MANUAL_PRINT.md",
    [string]$OutputDir = "docs/exports",
    [string]$BaseName = "OVS_USER_MANUAL",
    [string]$Formats = "pdf,docx,html",
    [string]$Title = "OVS User Manual",
    [string]$Author = "OVS Project Team",
    [switch]$Strict
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    $root = (Resolve-Path -Path ".").Path
    return [System.IO.Path]::GetFullPath((Join-Path $root $PathValue))
}

function Get-CommandPath {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string[]]$FallbackPaths = @()
    )
    $command = Get-Command -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        foreach ($path in $FallbackPaths) {
            if ($path -and (Test-Path -Path $path -PathType Leaf)) {
                return $path
            }
        }
        return $null
    }
    return $command.Source
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Fail-OrWarn {
    param([string]$Message)
    if ($Strict.IsPresent) {
        throw $Message
    }
    Write-Warn $Message
}

$resolvedInput = Resolve-ProjectPath -PathValue $InputPath
$resolvedOutputDir = Resolve-ProjectPath -PathValue $OutputDir

if (-not (Test-Path -Path $resolvedInput -PathType Leaf)) {
    throw "Input file not found: $resolvedInput"
}

if (-not (Test-Path -Path $resolvedOutputDir -PathType Container)) {
    New-Item -Path $resolvedOutputDir -ItemType Directory -Force | Out-Null
}

$pandocFallbacks = @(
    "$env:LOCALAPPDATA\Pandoc\pandoc.exe",
    "C:\Program Files\Pandoc\pandoc.exe",
    "C:\Program Files (x86)\Pandoc\pandoc.exe"
)
$pandoc = Get-CommandPath -Name "pandoc" -FallbackPaths $pandocFallbacks
if (-not $pandoc) {
    throw "Pandoc is required but was not found in PATH. Install from https://pandoc.org/installing.html"
}

Write-Info "Using input: $resolvedInput"
Write-Info "Output directory: $resolvedOutputDir"
Write-Info "Pandoc: $pandoc"

$requestedFormats = $Formats.Split(",") | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ }
if ($requestedFormats.Count -eq 0) {
    throw "No output formats requested."
}

$supported = @("pdf", "docx", "html")
foreach ($format in $requestedFormats) {
    if ($supported -notcontains $format) {
        throw "Unsupported format '$format'. Supported: $($supported -join ', ')"
    }
}

$commonArgs = @(
    "--standalone",
    "--toc",
    "--metadata", "title=$Title",
    "--metadata", "author=$Author",
    "--from", "gfm",
    "--resource-path", (Split-Path -Path $resolvedInput -Parent)
)

$exported = New-Object System.Collections.Generic.List[string]

if ($requestedFormats -contains "docx") {
    $docxOut = Join-Path $resolvedOutputDir "$BaseName.docx"
    & $pandoc @commonArgs $resolvedInput "--output=$docxOut"
    $exported.Add($docxOut)
    Write-Info "Generated DOCX: $docxOut"
}

if ($requestedFormats -contains "html") {
    $htmlOut = Join-Path $resolvedOutputDir "$BaseName.html"
    & $pandoc @commonArgs $resolvedInput "--output=$htmlOut"
    $exported.Add($htmlOut)
    Write-Info "Generated HTML: $htmlOut"
}

if ($requestedFormats -contains "pdf") {
    $pdfOut = Join-Path $resolvedOutputDir "$BaseName.pdf"

    # Try a common PDF engine sequence.
    $pdfEngines = @("xelatex", "wkhtmltopdf", "pdflatex")
    $selectedEngine = $null
    $selectedEnginePath = $null
    $pdfEngineFallbackMap = @{
        "xelatex"    = @("$env:ProgramFiles\MiKTeX\miktex\bin\x64\xelatex.exe", "C:\texlive\2024\bin\win32\xelatex.exe")
        "wkhtmltopdf" = @("C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
        "pdflatex"   = @("$env:ProgramFiles\MiKTeX\miktex\bin\x64\pdflatex.exe", "C:\texlive\2024\bin\win32\pdflatex.exe")
    }

    foreach ($engine in $pdfEngines) {
        $fallbacks = @()
        if ($pdfEngineFallbackMap.ContainsKey($engine)) {
            $fallbacks = $pdfEngineFallbackMap[$engine]
        }
        $resolvedEngine = Get-CommandPath -Name $engine -FallbackPaths $fallbacks
        if ($resolvedEngine) {
            $selectedEngine = $engine
            $selectedEnginePath = $resolvedEngine
            break
        }
    }

    if (-not $selectedEngine) {
        Fail-OrWarn "No PDF engine found (xelatex/wkhtmltopdf/pdflatex). Skipping PDF export."
    }
    else {
        try {
            & $pandoc @commonArgs $resolvedInput "--pdf-engine=$selectedEnginePath" "--output=$pdfOut"
            $exported.Add($pdfOut)
            Write-Info "Generated PDF via ${selectedEngine} (${selectedEnginePath}): $pdfOut"
        }
        catch {
            Fail-OrWarn "PDF export failed with engine '$selectedEngine'. Error: $($_.Exception.Message)"
        }
    }
}

if ($exported.Count -eq 0) {
    throw "No artifacts were exported."
}

Write-Info "Export complete."
Write-Info "Artifacts:"
foreach ($artifact in $exported) {
    Write-Host " - $artifact"
}
