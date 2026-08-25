import { build } from "esbuild";
import { cp, mkdir, readFile, rm } from "node:fs/promises";

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await build({
  entryPoints: ["src/sidepanel.ts", "src/options.ts", "src/service-worker.ts", "src/print.ts"],
  outdir: "dist",
  bundle: true,
  format: "iife",
  target: "chrome120",
  sourcemap: false,
});
for (const file of ["manifest.json", "managed-storage-schema.json", "sidepanel.html", "options.html", "print.html", "styles.css", "print.css"]) {
  await cp(file, `dist/${file}`);
}

// Ein Knopf ohne Ereignisbehandler faellt im Betrieb nicht auf: Der Klick tut
// einfach nichts. Genau das ist beim Ausbau des PDF-Wegs passiert, deshalb
// prueft der Build es jetzt.
for (const [seite, skript] of [["sidepanel.html", "sidepanel.js"], ["print.html", "print.js"], ["options.html", "options.js"]]) {
  const markup = await readFile(seite, "utf8");
  const code = await readFile(`dist/${skript}`, "utf8");
  const knoepfe = [...markup.matchAll(/<button[^>]*\sid="([^"]+)"/g)].map((treffer) => treffer[1]);
  const ohneBehandler = knoepfe.filter((id) => !code.includes(id));
  if (ohneBehandler.length > 0) {
    throw new Error(`${seite}: Knopf ohne Behandler in ${skript}: ${ohneBehandler.join(", ")}`);
  }
  console.log(`  ${seite}: ${knoepfe.length} Knopf/Knoepfe, alle verdrahtet`);
}
