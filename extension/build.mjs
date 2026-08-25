import { build } from "esbuild";
import { cp, mkdir, rm } from "node:fs/promises";

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
