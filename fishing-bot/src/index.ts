import { resolve } from "node:path";

import { createFishingBot } from "./bot.js";
import { FishingService } from "./service.js";
import { FishingStore } from "./store.js";

const token = process.env.FISHING_BOT_TOKEN ?? process.env.TELEGRAM_TOKEN;
if (!token) {
  throw new Error("FISHING_BOT_TOKEN (or TELEGRAM_TOKEN for standalone use) is required");
}

const dataDirectory = process.env.BOT_DATA_DIR ?? "data";
const dataFile = process.env.FISHING_DATA_FILE ?? resolve(dataDirectory, "fishing.json");
const service = new FishingService(new FishingStore(dataFile));
const bot = createFishingBot(token, service);

bot.catch((error) => {
  console.error("Fishing update failed", error.error);
});

try {
  await bot.api.setMyCommands([
    { command: "fish", description: "Open your Lake Ontario fishing camp" },
    { command: "gear", description: "Manage rods, lures, and bait" },
    { command: "collection", description: "View and sell your fish" },
  ]);
} catch (error) {
  console.error("Unable to register fishing bot commands; continuing to poll", error);
}

console.log(`Fishing bot ready; persisting anglers in ${dataFile}`);
await bot.start({ onStart: () => console.log("Fishing bot polling started") });
