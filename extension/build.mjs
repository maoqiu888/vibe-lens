import esbuild from "esbuild";
import { cp, mkdir, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";

const watch = process.argv.includes("--watch");
const outdir = "build";

// Plugin: inline a CSS file as a string export at build time
const inlineCss = {
  name: "inline-css",
  setup(build) {
    build.onResolve({ filter: /\.css\?inline$/ }, (args) => ({
      path: join(dirname(args.importer), args.path.replace("?inline", "")),
      namespace: "inline-css",
    }));
    build.onLoad({ filter: /.*/, namespace: "inline-css" }, async (args) => {
      const css = await readFile(args.path, "utf8");
      return { contents: `export default ${JSON.stringify(css)};`, loader: "js" };
    });
  },
};

await mkdir(outdir, { recursive: true });
await mkdir(join(outdir, "popup"), { recursive: true });

// Copy static assets
await cp("manifest.json", join(outdir, "manifest.json"));
await cp("src/assets", join(outdir, "assets"), { recursive: true });
if (existsSync("src/popup/popup.html")) {
  await cp("src/popup/popup.html", join(outdir, "popup/popup.html"));
}
if (existsSync("src/popup/popup.css")) {
  await cp("src/popup/popup.css", join(outdir, "popup/popup.css"));
}

const ctx = {
  bundle: true,
  format: "iife",
  target: "chrome114",
  plugins: [inlineCss],
  logLevel: "info",
};

const entries = [];
if (existsSync("src/background/index.ts")) {
  entries.push(esbuild.build({ ...ctx, entryPoints: ["src/background/index.ts"], outfile: join(outdir, "background.js") }));
}
if (existsSync("src/content/index.ts")) {
  entries.push(esbuild.build({ ...ctx, entryPoints: ["src/content/index.ts"], outfile: join(outdir, "content.js") }));
}
if (existsSync("src/popup/popup.ts")) {
  entries.push(esbuild.build({ ...ctx, entryPoints: ["src/popup/popup.ts"], outfile: join(outdir, "popup/popup.js") }));
}
await Promise.all(entries);

if (watch) {
  console.log("Built once. Re-run `npm run build` after edits.");
}

console.log("Extension built to", outdir);
