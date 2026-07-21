import { createServer } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "out");
const port = Number(process.env.PORT ?? 3001);
const basePath = process.env.DEMO_DEPLOY_TARGET === "vercel" ? "" : `/${process.env.GITHUB_PAGES_BASE_PATH ?? "UtilitiesPlatform"}`;
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png" };

createServer((request, response) => {
  const rawPath = decodeURIComponent(new URL(request.url ?? "/", `http://localhost:${port}`).pathname);
  const path = rawPath.startsWith(basePath) ? rawPath.slice(basePath.length) || "/" : rawPath;
  let filePath = normalize(join(root, path));
  if (!filePath.startsWith(root)) {
    response.writeHead(403).end("Forbidden");
    return;
  }
  if (!existsSync(filePath)) filePath = join(root, path, "index.html");
  if (existsSync(filePath) && statSync(filePath).isDirectory()) filePath = join(filePath, "index.html");
  if (!existsSync(filePath)) filePath = join(root, "index.html");
  response.writeHead(200, { "content-type": types[extname(filePath)] ?? "application/octet-stream" });
  response.end(readFileSync(filePath));
}).listen(port, () => console.log(`Demo export available at http://127.0.0.1:${port}${basePath || ""}/`));
