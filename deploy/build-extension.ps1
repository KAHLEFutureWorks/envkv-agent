<#
.SYNOPSIS
    Baut die Erweiterung und signiert sie zu einem .crx fuer die Selbstauslieferung.

.DESCRIPTION
    Erwartet die Signaturdatei (.pem) als Parameter. Diese Datei ist der
    Schluessel zur Identitaet der Erweiterung: Geht sie verloren, aendert sich
    die Kennung und jede Geraeterichtlinie muss neu geschrieben werden. Sie
    gehoert in den Passwortmanager der IT und niemals in dieses Verzeichnis.

    Das Ergebnis liegt in deploy\dist\releases und wird von dort auf den Server
    kopiert.

.EXAMPLE
    .\deploy\build-extension.ps1 -PemPath C:\sicher\kahle-envkv-agent.pem
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PemPath,

    [string]$EdgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$extension = Join-Path $repo "extension"

if (-not (Test-Path -LiteralPath $PemPath)) {
    throw "Die Signaturdatei wurde nicht gefunden: $PemPath"
}
if (-not (Test-Path -LiteralPath $EdgePath)) {
    throw "Edge wurde nicht gefunden: $EdgePath. Pfad mit -EdgePath angeben."
}

# Die Signaturdatei darf nicht im Projektverzeichnis liegen; von dort koennte
# sie versehentlich in die Versionsverwaltung oder in ein Paket geraten.
$pemVoll = (Resolve-Path -LiteralPath $PemPath).Path
if ($pemVoll.StartsWith($repo, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Die Signaturdatei liegt im Projektverzeichnis ($pemVoll). Bitte ausserhalb ablegen."
}

Write-Host "==> Erweiterung bauen" -ForegroundColor Cyan
Push-Location $extension
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "Der Build der Erweiterung ist fehlgeschlagen." }
}
finally { Pop-Location }

$manifest = Get-Content (Join-Path $extension "dist\manifest.json") -Raw | ConvertFrom-Json
$version = $manifest.version
if (-not $manifest.key) {
    Write-Warning "manifest.json enthaelt kein Feld 'key'. Die Kennung der entpackt geladenen Erweiterung weicht dann von der ausgelieferten ab."
}
Write-Host "    Fassung: $version"

$ziel = Join-Path $repo "deploy\dist\releases"
New-Item -ItemType Directory -Force -Path $ziel | Out-Null

$ausgabe = Join-Path $ziel "kahle-envkv-agent-$version.crx"
if (Test-Path -LiteralPath $ausgabe) {
    throw "Es gibt bereits ein Paket dieser Fassung: $ausgabe. Bitte zuerst die Versionsnummer in extension\manifest.json erhoehen."
}

Write-Host "==> Paket signieren" -ForegroundColor Cyan
$distDir = Join-Path $extension "dist"
$erzeugt = Join-Path $extension "dist.crx"
if (Test-Path -LiteralPath $erzeugt) { Remove-Item -LiteralPath $erzeugt -Force }

# Ein eigenes Profilverzeichnis erzwingt einen neuen Edge-Prozess. Andernfalls
# reicht ein laufendes Edge den Aufruf an sich selbst weiter und packt nichts.
$profil = Join-Path $env:TEMP ("envkv-pack-" + [guid]::NewGuid().ToString("N"))
try {
    & $EdgePath "--pack-extension=$distDir" "--pack-extension-key=$pemVoll" `
        "--user-data-dir=$profil" "--no-message-box" | Out-Null
    for ($i = 0; $i -lt 60 -and -not (Test-Path -LiteralPath $erzeugt); $i++) {
        Start-Sleep -Milliseconds 500
    }
}
finally {
    if (Test-Path -LiteralPath $profil) {
        try { Remove-Item -LiteralPath $profil -Recurse -Force -ErrorAction Stop } catch {}
    }
}

if (-not (Test-Path -LiteralPath $erzeugt)) {
    throw "Edge hat kein Paket erzeugt. Ersatzweise ueber edge://extensions -> 'Erweiterung packen' signieren."
}

Move-Item -LiteralPath $erzeugt -Destination $ausgabe
# Edge legt bei jedem Packen eine .pem daneben, falls keine uebergeben wurde.
# Hier wurde eine uebergeben; trotzdem zur Sicherheit pruefen und entfernen.
$streu = Join-Path $extension "dist.pem"
if (Test-Path -LiteralPath $streu) { Remove-Item -LiteralPath $streu -Force }

$hash = (Get-FileHash -LiteralPath $ausgabe -Algorithm SHA256).Hash
$groesse = [math]::Round((Get-Item -LiteralPath $ausgabe).Length / 1KB, 1)

Write-Host ""
Write-Host "Fertig." -ForegroundColor Green
Write-Host "  Datei:  $ausgabe"
Write-Host "  Groesse: $groesse KB"
Write-Host "  SHA256: $hash"
Write-Host ""
Write-Host "Naechster Schritt - auf den Server kopieren:"
Write-Host "  scp `"$ausgabe`" joltmanns@vinci-prod-01:~/"
Write-Host "  ssh joltmanns@vinci-prod-01 'sudo mv ~/kahle-envkv-agent-$version.crx /opt/envkv/releases/ && sudo chmod 644 /opt/envkv/releases/kahle-envkv-agent-$version.crx'"
