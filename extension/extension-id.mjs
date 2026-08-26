/**
 * Leitet Kennung und Manifest-Schluessel aus der Signaturdatei ab.
 *
 * Chromium bildet die Kennung einer Erweiterung aus dem oeffentlichen Teil des
 * Signaturschluessels. Sie bleibt deshalb ueber alle Fassungen gleich - solange
 * dieselbe .pem verwendet wird. Geht die .pem verloren, aendert sich die
 * Kennung, und jede Richtlinie muss neu geschrieben werden.
 *
 *   node extension-id.mjs ..\pfad\kahle-envkv-agent.pem [--write]
 *
 * --write traegt den oeffentlichen Schluessel als "key" in manifest.json ein.
 * Der private Teil der Datei wird dabei niemals gelesen, ausgegeben oder
 * gespeichert.
 */
import { createHash, createPublicKey } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const [pemPath, ...flags] = process.argv.slice(2);
if (!pemPath) {
  console.error("Aufruf: node extension-id.mjs <pfad-zur-pem> [--write]");
  process.exit(1);
}

const pem = await readFile(pemPath, "utf8");
const spki = createPublicKey(pem).export({ type: "spki", format: "der" });
const base64 = spki.toString("base64");

// Erste 16 Byte des SHA-256 ueber den DER-Schluessel, hexadezimal, dann
// Ziffer fuer Ziffer von 0-f nach a-p verschoben.
const digest = createHash("sha256").update(spki).digest("hex").slice(0, 32);
const id = [...digest].map((zeichen) => "abcdefghijklmnop"[parseInt(zeichen, 16)]).join("");

console.log(`Kennung der Erweiterung: ${id}`);
console.log(`Manifest-Schluessel:     ${base64}`);

if (flags.includes("--write")) {
  const datei = new URL("./manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(datei, "utf8"));
  if (manifest.key && manifest.key !== base64) {
    // Ein abweichender Schluessel im Manifest laesst Edge die Installation mit
    // einer schwer deutbaren Meldung abbrechen. Lieber hier abbrechen.
    console.error("manifest.json enthaelt bereits einen anderen Schluessel. Bitte pruefen.");
    process.exit(1);
  }
  const { manifest_version, name, version, ...rest } = manifest;
  const neu = { manifest_version, name, version, key: base64, ...rest };
  await writeFile(datei, JSON.stringify(neu, null, 2) + "\n", "utf8");
  console.log("manifest.json wurde ergaenzt.");
}
