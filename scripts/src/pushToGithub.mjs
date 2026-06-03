import fs from "fs";
import path from "path";
import https from "https";
import { fileURLToPath } from "url";

const TOKEN = process.env.GITHUB_TOKEN;
const OWNER = "yasir069-cs";
const REPO = "crypto-futures-intelligence-bot";
const BRANCH = "main";
const ROOT = path.resolve(fileURLToPath(import.meta.url), "../../..");

// Only push these directories/files — skip generated UI boilerplate
const INCLUDE_PATHS = [
  "artifacts/api-server/src",
  "scripts/src/pushToGithub.mjs",
  "artifacts/api-server/package.json",
  "artifacts/api-server/tsconfig.json",
  "artifacts/api-server/build.mjs",
  "artifacts/crypto-detector/src/App.tsx",
  "artifacts/crypto-detector/src/index.css",
  "artifacts/crypto-detector/src/pages",
  "artifacts/crypto-detector/src/hooks",
  "artifacts/crypto-detector/src/lib",
  "artifacts/crypto-detector/package.json",
  "artifacts/crypto-detector/tsconfig.json",
  "artifacts/crypto-detector/vite.config.ts",
  "artifacts/crypto-detector/index.html",
  "lib/api-spec/openapi.yaml",
  "lib/api-client-react/src/generated",
  "lib/api-client-react/package.json",
  "lib/api-zod/src/generated",
  "lib/api-zod/package.json",
  "lib/db/src/schema",
  "lib/db/package.json",
  "pnpm-workspace.yaml",
  "package.json",
  "tsconfig.json",
  "tsconfig.base.json",
  "replit.md",
];

const EXCLUDE_EXT = new Set([".map", ".tsbuildinfo", ".lock"]);
const EXCLUDE_FILES = new Set(["pnpm-lock.yaml"]);

function api(method, urlPath, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = https.request(
      {
        hostname: "api.github.com",
        path: urlPath,
        method,
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "replit-agent",
          "X-GitHub-Api-Version": "2022-11-28",
          ...(data ? { "Content-Length": Buffer.byteLength(data) } : {}),
        },
      },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => resolve({ body: JSON.parse(buf), status: res.statusCode }));
      }
    );
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

function collectFiles() {
  const result = [];
  for (const inc of INCLUDE_PATHS) {
    const full = path.join(ROOT, inc);
    if (!fs.existsSync(full)) continue;
    const stat = fs.statSync(full);
    if (stat.isFile()) {
      if (!EXCLUDE_FILES.has(path.basename(full)) && !EXCLUDE_EXT.has(path.extname(full))) {
        try { result.push([inc, fs.readFileSync(full)]); } catch (e) {}
      }
    } else {
      // directory — walk it
      const walk = (dir) => {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          const fp = path.join(dir, entry.name);
          const rel = path.relative(ROOT, fp);
          if (entry.isDirectory()) { walk(fp); }
          else {
            if (EXCLUDE_FILES.has(entry.name)) continue;
            if (EXCLUDE_EXT.has(path.extname(entry.name))) continue;
            try { result.push([rel, fs.readFileSync(fp)]); } catch (e) {}
          }
        }
      };
      walk(full);
    }
  }
  return result;
}

async function main() {
  if (!TOKEN) { console.error("GITHUB_TOKEN not set"); process.exit(1); }

  const files = collectFiles();
  console.log(`Pushing ${files.length} files to GitHub...`);

  let baseSha = null, baseTree = null;
  const refRes = await api("GET", `/repos/${OWNER}/${REPO}/git/ref/heads/${BRANCH}`);
  if (refRes.status === 200) {
    baseSha = refRes.body.object.sha;
    const cr = await api("GET", `/repos/${OWNER}/${REPO}/git/commits/${baseSha}`);
    baseTree = cr.body.tree.sha;
    console.log(`Base: ${baseSha.slice(0, 8)}`);
  } else {
    console.log("Empty repo — fresh push");
  }

  const treeItems = [];
  for (let i = 0; i < files.length; i++) {
    const [filePath, content] = files[i];
    const r = await api("POST", `/repos/${OWNER}/${REPO}/git/blobs`, {
      content: content.toString("base64"),
      encoding: "base64",
    });
    if (r.status === 201 || r.status === 200) {
      treeItems.push({ path: filePath.replace(/\\/g, "/"), mode: "100644", type: "blob", sha: r.body.sha });
    } else {
      console.log(`  SKIP ${filePath} (${r.status})`);
    }
    if ((i + 1) % 10 === 0) process.stdout.write(`  ${i + 1}/${files.length}\r`);
  }

  console.log(`\nCreating tree (${treeItems.length} items)...`);
  const treeBody = { tree: treeItems };
  if (baseTree) treeBody.base_tree = baseTree;
  const treeRes = await api("POST", `/repos/${OWNER}/${REPO}/git/trees`, treeBody);
  if (![200, 201].includes(treeRes.status)) { console.error("Tree failed:", treeRes.body.message); process.exit(1); }

  const commitBody = {
    message: "feat: CryptoDetect — crypto signal detector with CoinGecko, React, Express\n\n- Real-time Buy Long / Sell Short signals from CoinGecko free API\n- Signal scoring: 24h momentum, 7d trend, volume spikes, ATH distance\n- In-memory caching to stay within CoinGecko rate limits\n- Dashboard with market summary, top signals, coin scanner\n- Coin detail page with 7-day sparkline chart\n- API: /coins, /coins/:id, /signals, /market-summary, /top-signals",
    tree: treeRes.body.sha,
  };
  if (baseSha) commitBody.parents = [baseSha];
  const commitRes = await api("POST", `/repos/${OWNER}/${REPO}/git/commits`, commitBody);
  if (![200, 201].includes(commitRes.status)) { console.error("Commit failed:", commitRes.body.message); process.exit(1); }

  const newSha = commitRes.body.sha;
  const refUp = baseSha
    ? await api("PATCH", `/repos/${OWNER}/${REPO}/git/refs/heads/${BRANCH}`, { sha: newSha, force: true })
    : await api("POST", `/repos/${OWNER}/${REPO}/git/refs`, { ref: `refs/heads/${BRANCH}`, sha: newSha });

  if ([200, 201].includes(refUp.status)) {
    console.log(`\nSUCCESS! ${treeItems.length} files → https://github.com/${OWNER}/${REPO}`);
  } else {
    console.error("Ref update failed:", refUp.body.message);
    process.exit(1);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
