import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const apiBase = process.env.DATA_API_URL || "http://localhost:8080";
const outDir = resolve(process.cwd(), "src/data");

async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`fetch ${path} -> ${res.status}`);
  }
  return res.json();
}

async function main() {
  await mkdir(outDir, { recursive: true });

  let blocks = [];
  let listings = [];

  try {
    blocks = await fetchJSON(`${apiBase}/blocks`);
  } catch (err) {
    console.warn("warn: blocks fetch failed:", err.message);
  }

  try {
    listings = await fetchJSON(
      `${apiBase}/listings?limit=500&sort=listing_date_desc`
    );
  } catch (err) {
    console.warn("warn: listings fetch failed:", err.message);
  }

  await writeFile(
    resolve(outDir, "blocks.json"),
    JSON.stringify(blocks ?? [], null, 2),
    "utf8"
  );
  await writeFile(
    resolve(outDir, "listings.json"),
    JSON.stringify(listings ?? [], null, 2),
    "utf8"
  );

  console.log(
    `data written: ${blocks?.length ?? 0} blocks, ${listings?.length ?? 0} listings`
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

