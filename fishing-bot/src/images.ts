import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { FishSpecies } from "./domain.js";

const imageCache = new Map<string, string>();

export function equipmentArtPath(kind: "rod" | "lure" | "bait"): string {
  const moduleDirectory = dirname(fileURLToPath(import.meta.url));
  const sourceAsset = resolve(moduleDirectory, "../assets", `${kind}-collection.png`);
  if (existsSync(sourceAsset)) return sourceAsset;
  return resolve(moduleDirectory, "../../assets", `${kind}-collection.png`);
}

export async function wikipediaImageFor(fish: FishSpecies): Promise<string> {
  const cached = imageCache.get(fish.id);
  if (cached) return cached;

  try {
    const endpoint = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(fish.wikipediaPage)}`;
    const response = await fetch(endpoint, {
      headers: { "User-Agent": "boom-bot-fishing/1.0 (Telegram game)" },
      signal: AbortSignal.timeout(4500),
    });
    if (response.ok) {
      const payload = (await response.json()) as {
        originalimage?: { source?: string };
        thumbnail?: { source?: string };
      };
      const source = payload.originalimage?.source ?? payload.thumbnail?.source;
      if (source) {
        imageCache.set(fish.id, source);
        return source;
      }
    }
  } catch {
    // Telegram can still follow the stable Wikipedia Special:FilePath fallback.
  }

  imageCache.set(fish.id, fish.fallbackImageUrl);
  return fish.fallbackImageUrl;
}
