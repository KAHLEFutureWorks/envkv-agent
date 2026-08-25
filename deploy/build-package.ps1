<#
.SYNOPSIS
    Baut ein Auslieferungspaket des KAHLE EnVKV Agent für den Server.

.DESCRIPTION
    Das Paket enthält exakt den Stand eines Git-Commits. Dadurch ist später
    nachvollziehbar, welcher Code eine bestimmte Ausgabe erzeugt hat.

    Der Arbeitsbaum muss sauber sein; sonst entstünde ein Paket, das keinem
    nachvollziehbaren Stand entspricht.

.EXAMPLE
    .\deploy\build-package.ps1
#>

[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "dist")
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
Set-Location $repository

Write-Host "==> Arbeitsbaum prüfen" -ForegroundColor Cyan
$dirty = git status --porcelain
if ($dirty) {
    Write-Host $dirty
    throw "Der Arbeitsbaum enthält nicht eingecheckte Änderungen. Bitte zuerst committen, damit das Paket einem Stand entspricht."
}

$commit = (git rev-parse HEAD).Trim()
$short = (git rev-parse --short HEAD).Trim()
$stamp = Get-Date -Format "yyyyMMdd"
$name = "envkv-agent-$stamp-$short"

Write-Host "    Commit: $commit"

if (-not (Test-Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
}
$archive = Join-Path $OutputDirectory "$name.tar.gz"

Write-Host "==> Paket erzeugen" -ForegroundColor Cyan
# git archive nimmt ausschliesslich versionierte Dateien auf. Zugangsdaten,
# Auditdaten und lokale Umgebungen koennen dadurch nicht in das Paket geraten.
git archive --format=tar.gz --prefix="$name/" -o $archive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive ist fehlgeschlagen." }

$hash = (Get-FileHash -Algorithm SHA256 $archive).Hash.ToLower()
$size = [math]::Round((Get-Item $archive).Length / 1MB, 2)

Write-Host "==> Fertig" -ForegroundColor Cyan
Write-Host "    Datei:  $archive"
Write-Host "    Groesse: $size MB"
Write-Host "    SHA256: $hash"

$hash | Out-File -FilePath "$archive.sha256" -Encoding ascii -NoNewline

Write-Host ""
Write-Host "Naechste Schritte:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  scp -i `"`$env:USERPROFILE\.ssh\kahle-vinci-admin`" -o IdentitiesOnly=yes ``"
Write-Host "    `"$archive`" ``"
Write-Host "    joltmanns@152.53.158.166:/tmp/$name.tar.gz"
Write-Host ""
Write-Host "  Danach auf dem Server:"
Write-Host ""
Write-Host "    cd /tmp"
Write-Host "    sha256sum $name.tar.gz"
Write-Host "    tar -xzf $name.tar.gz"
Write-Host "    cd $name"
Write-Host "    sudo bash install.sh"
Write-Host ""
