<#
.SYNOPSIS
    Hinterlegt Adresse und Zugriffsschluessel des EnVKV-Dienstes fuer die Edge-Erweiterung.

.DESCRIPTION
    Wird in Intune als Plattformskript im Geraetekontext ausgefuehrt. Die
    Erweiterung liest diese Werte ueber chrome.storage.managed; Mitarbeitende
    muessen dann nichts mehr eintragen und koennen die Werte auch nicht aendern.

    Vor dem Hochladen nach Intune muss $ApiKey mit dem Wert aus der .env des
    Servers gefuellt werden:

        sudo grep '^EXTENSION_API_KEY=' /opt/envkv/.env

    Hinweis: Der Schluessel liegt danach in der Registry jedes Geraets und ist
    dort fuer angemeldete Benutzer lesbar. Das ist fuer den Pilotbetrieb
    vertretbar, ersetzt aber keine Benutzeranmeldung.
#>

$ExtensionId = "HIER_DIE_KENNUNG_EINTRAGEN"
$ApiUrl      = "https://envkv.kahle.de"
$ApiKey      = "HIER_DEN_SCHLUESSEL_EINTRAGEN"

$ErrorActionPreference = "Stop"

if ($ExtensionId -notmatch '^[a-p]{32}$') {
    throw "Die Kennung der Erweiterung ist nicht ausgefuellt oder ungueltig."
}
if ($ApiKey -eq "HIER_DEN_SCHLUESSEL_EINTRAGEN" -or [string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "Der Zugriffsschluessel ist nicht ausgefuellt."
}

$pfad = "HKLM:\SOFTWARE\Policies\Microsoft\Edge\3rdparty\extensions\$ExtensionId\policy"
if (-not (Test-Path -LiteralPath $pfad)) {
    New-Item -Path $pfad -Force | Out-Null
}
New-ItemProperty -LiteralPath $pfad -Name "apiUrl" -Value $ApiUrl -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $pfad -Name "apiKey" -Value $ApiKey -PropertyType String -Force | Out-Null

# Der Schluessel wird bewusst nicht ausgegeben; die Protokolle von Intune
# blieben sonst dauerhaft lesbar.
Write-Output "Verbindung fuer $ExtensionId hinterlegt ($ApiUrl)."
