import { Bot, Context, InlineKeyboard, InputFile } from "grammy";

import {
  BAIT_LIST,
  BaitId,
  formatWeight,
  fishById,
  LURE_LIST,
  LureId,
  ROD_LIST,
  RodId,
} from "./domain.js";
import { equipmentArtPath, wikipediaImageFor } from "./images.js";
import { catalogCounts, collectionSummary, FishingService, gearFor } from "./service.js";

type GearKind = "rod" | "lure" | "bait";
type CallbackAction = "home" | "gear" | "collection" | "shop" | "art" | "cast" | "repair" | "sellall" | "buy" | "equip" | "sell";

interface ParsedCallback {
  ownerId: string;
  action: CallbackAction;
  kind?: GearKind;
  id?: string;
}

function displayName(ctx: Context): string {
  if (!ctx.from) return "Angler";
  const fullName = [ctx.from.first_name, ctx.from.last_name].filter(Boolean).join(" ");
  return (fullName || ctx.from.username || "Angler").replace(/\s+/g, " ").trim().slice(0, 64) || "Angler";
}

function markdownV1(text: string): string {
  return [...text].map((character) => "_*[]()\\".includes(character) ? `\\${character}` : character).join("");
}

function ownerId(ctx: Context): string {
  return String(ctx.from?.id ?? "");
}

function callback(owner: string, action: CallbackAction, kind?: string, id?: string): string {
  if (action === "sell") return ["fish", owner, action, id ?? ""].join("|");
  return ["fish", owner, action, kind, id].filter((part): part is string => Boolean(part)).join("|");
}

function parseCallback(data: string): ParsedCallback | null {
  const [prefix, owner, action, kind, id] = data.split("|");
  if (prefix !== "fish" || !owner || !action) return null;
  if (!["home", "gear", "collection", "shop", "art", "cast", "repair", "sellall", "buy", "equip", "sell"].includes(action)) return null;
  if (action === "sell") return { ownerId: owner, action: "sell", id: kind };
  if (kind && !["rod", "lure", "bait"].includes(kind)) return null;
  return { ownerId: owner, action: action as CallbackAction, kind: kind as GearKind | undefined, id };
}

function homeKeyboard(userId: string): InlineKeyboard {
  return new InlineKeyboard()
    .text("🎣 Cast a line", callback(userId, "cast"))
    .text("🧰 Tackle box", callback(userId, "gear"))
    .row()
    .text("🐟 Collection", callback(userId, "collection"))
    .text("🛒 Shop", callback(userId, "shop"));
}

function actionKeyboard(userId: string): InlineKeyboard {
  return new InlineKeyboard()
    .text("🎣 Cast again", callback(userId, "cast"))
    .text("🐟 Collection", callback(userId, "collection"))
    .row()
    .text("🧰 Tackle box", callback(userId, "gear"))
    .text("🏕️ Camp", callback(userId, "home"));
}

function homeCaption(service: FishingService, ctx: Context): string {
  const player = service.player(ownerId(ctx), displayName(ctx));
  const gear = gearFor(player);
  const counts = catalogCounts(player);
  return [
    "🌊 *Lake Ontario Angler*",
    "",
    `Welcome back, ${markdownV1(player.displayName)}. The lake is glassy and something large just rolled beyond the reeds.`,
    "",
    `💰 ${player.gold} gold  ·  🎒 ${counts.bait} bait  ·  🐟 ${player.totalFish} fish landed`,
    `🎋 ${gear.rod.name} (${player.rods[gear.rod.id].condition}% condition)`,
    `🪝 ${gear.lure.name}  ·  🪱 ${gear.bait.name} × ${player.bait[gear.bait.id]}`,
    "",
    "Big fish pay better, but they are moody, slippery, and occasionally vindictive toward fishing rods.",
  ].join("\n");
}

function gearKeyboard(service: FishingService, ctx: Context): InlineKeyboard {
  const userId = ownerId(ctx);
  const player = service.player(userId, displayName(ctx));
  const keyboard = new InlineKeyboard();
  keyboard.text("🎋 RODS", callback(userId, "gear")).row();
  for (const rod of ROD_LIST) {
    const inventory = player.rods[rod.id];
    const equipped = player.equipped.rod === rod.id;
    const label = inventory.owned
      ? `${equipped ? "✅" : "🎋"} ${rod.name} · ${inventory.condition}%`
      : `🛒 ${rod.name} · ${rod.price}g`;
    keyboard.text(label, inventory.owned ? callback(userId, "equip", "rod", rod.id) : callback(userId, "buy", "rod", rod.id)).row();
  }
  keyboard.text("🪝 LURES", callback(userId, "gear")).row();
  for (const lure of LURE_LIST) {
    const owned = player.lures[lure.id];
    keyboard.text(owned ? `${player.equipped.lure === lure.id ? "✅" : "🪝"} ${lure.name}` : `🛒 ${lure.name} · ${lure.price}g`, owned ? callback(userId, "equip", "lure", lure.id) : callback(userId, "buy", "lure", lure.id)).row();
  }
  keyboard.text("🪱 BAIT", callback(userId, "gear")).row();
  for (const bait of BAIT_LIST) {
    const quantity = player.bait[bait.id];
    if (quantity > 0) {
      keyboard.text(`${player.equipped.bait === bait.id ? "✅" : "🪱"} ${bait.name} × ${quantity}`, callback(userId, "equip", "bait", bait.id));
    }
    keyboard.text(`➕ ${bait.name} · ${bait.packSize} for ${bait.price}g`, callback(userId, "buy", "bait", bait.id)).row();
  }
  if (player.rods[player.equipped.rod].condition <= 0) keyboard.text("🔧 Repair equipped rod", callback(userId, "repair")).row();
  keyboard.text("🎋 Rod art", callback(userId, "art", "rod")).text("🪝 Lure art", callback(userId, "art", "lure")).row();
  keyboard.text("🪱 Bait art", callback(userId, "art", "bait")).row();
  keyboard.text("🏕️ Back to camp", callback(userId, "home"));
  return keyboard;
}

function gearCaption(service: FishingService, ctx: Context): string {
  const player = service.player(ownerId(ctx), displayName(ctx));
  const gear = gearFor(player);
  return [
    "🧰 *Tackle Box*",
    "",
    `💰 ${player.gold} gold`,
    `🎋 Equipped: ${gear.rod.name} (${player.rods[gear.rod.id].condition}% condition)`,
    `🪝 Equipped: ${gear.lure.name}`,
    `🪱 Equipped: ${gear.bait.name} × ${player.bait[gear.bait.id]}`,
    "",
    "Owned tackle is reusable. Bait is consumed one cast at a time. Upgrade before chasing the lake monsters.",
  ].join("\n");
}

function collectionCaption(service: FishingService, ctx: Context): string {
  const player = service.player(ownerId(ctx), displayName(ctx));
  if (player.catches.length === 0) {
    return "🐟 *Fish Collection*\n\nYour livewell is empty. The lake is not impressed yet.";
  }
  const summary = collectionSummary(player)
    .map((entry) => `${entry.species.emoji} ${entry.species.name}: ${entry.count} · ${entry.totalWeightKg.toFixed(2)} kg`)
    .join("\n");
  const recent = player.catches.slice(0, 6)
    .map((fish) => `${fishById(fish.speciesId).emoji} ${fishById(fish.speciesId).name} · ${formatWeight(fish.weightKg)} · ${fish.value}g`)
    .join("\n");
  return [
    "🐟 *Fish Collection*",
    "",
    summary,
    "",
    "Recent catches:",
    recent,
    "",
    `💰 ${player.gold} gold  ·  🎣 ${player.totalCasts} casts  ·  🏆 Biggest: ${formatWeight(player.biggestFishKg)}`,
  ].join("\n");
}

function collectionKeyboard(service: FishingService, ctx: Context): InlineKeyboard {
  const player = service.player(ownerId(ctx), displayName(ctx));
  const userId = ownerId(ctx);
  const keyboard = new InlineKeyboard();
  for (const fish of player.catches.slice(0, 8)) {
    const species = fishById(fish.speciesId);
    keyboard.text(`💰 Sell ${species.name} · ${fish.value}g`, callback(userId, "sell", undefined, fish.id)).row();
  }
  if (player.catches.length > 0) keyboard.text("💰 Sell all fish", callback(userId, "sellall")).row();
  keyboard.text("🎣 Go fishing", callback(userId, "cast")).text("🏕️ Camp", callback(userId, "home"));
  return keyboard;
}

function resultCaption(service: FishingService, ctx: Context, lead: string): string {
  return `${lead}\n\n${homeCaption(service, ctx)}`;
}

async function editPanel(ctx: Context, text: string, keyboard: InlineKeyboard): Promise<void> {
  try {
    await ctx.editMessageCaption({ caption: text, parse_mode: "Markdown", reply_markup: keyboard });
  } catch {
    try {
      await ctx.editMessageText(text, { parse_mode: "Markdown", reply_markup: keyboard });
    } catch {
      await ctx.reply(text, { parse_mode: "Markdown", reply_markup: keyboard });
    }
  }
}

async function sendHome(ctx: Context, service: FishingService): Promise<void> {
  await ctx.replyWithPhoto(new InputFile(equipmentArtPath("rod")), {
    caption: homeCaption(service, ctx),
    parse_mode: "Markdown",
    reply_markup: homeKeyboard(ownerId(ctx)),
  });
}

async function sendGear(ctx: Context, service: FishingService): Promise<void> {
  await ctx.replyWithPhoto(new InputFile(equipmentArtPath("rod")), {
    caption: gearCaption(service, ctx),
    parse_mode: "Markdown",
    reply_markup: gearKeyboard(service, ctx),
  });
}

async function sendCollection(ctx: Context, service: FishingService): Promise<void> {
  await ctx.reply(collectionCaption(service, ctx), {
    parse_mode: "Markdown",
    reply_markup: collectionKeyboard(service, ctx),
  });
}

async function sendShop(ctx: Context, service: FishingService): Promise<void> {
  await editPanel(ctx, `🛒 *Tackle Shop*\n\n${gearCaption(service, ctx)}`, gearKeyboard(service, ctx));
}

async function castLine(ctx: Context, service: FishingService): Promise<void> {
  const result = service.cast(ownerId(ctx), displayName(ctx));
  if (result.kind === "caught") {
    const imageUrl = await wikipediaImageFor(result.species);
    const caption = [
      `${result.species.emoji} *FISH ON!*`,
      "",
      `You landed a *${result.species.name}* (${result.species.scientificName}).`,
      `⚖️ Weight: *${formatWeight(result.fish.weightKg)}*`,
      `💰 Sale value: *${result.fish.value} gold*`,
      `The catch is illustrated with the [Wikipedia image for ${result.species.name}](https://en.wikipedia.org/wiki/${encodeURIComponent(result.species.wikipediaPage.replaceAll(" ", "_"))}).`,
    ].join("\n");
    try {
      await ctx.replyWithPhoto(imageUrl, { caption, parse_mode: "Markdown", reply_markup: actionKeyboard(ownerId(ctx)) });
    } catch {
      await ctx.reply(caption, { parse_mode: "Markdown", reply_markup: actionKeyboard(ownerId(ctx)) });
    }
    return;
  }

  if (result.kind === "no_bait") {
    await editPanel(ctx, resultCaption(service, ctx, `🪱 You are out of ${result.bait.name}. Buy a fresh pack from the tackle box.`), gearKeyboard(service, ctx));
    return;
  }
  if (result.kind === "rod_broken") {
    await editPanel(ctx, resultCaption(service, ctx, `🔧 Your ${result.rod.name} is broken. Repair it before casting again.`), gearKeyboard(service, ctx));
    return;
  }
  if (result.kind === "broken") {
    await editPanel(ctx, resultCaption(service, ctx, `💥 The ${result.species.name} got away — and took your ${result.rod.name} with it. Dramatic.`), gearKeyboard(service, ctx));
    return;
  }
  await editPanel(ctx, resultCaption(service, ctx, `🌫️ You felt a ${result.species.name} tug, then the line went slack. The lake keeps its secrets.`), actionKeyboard(ownerId(ctx)));
}

export function createFishingBot(token: string, service: FishingService): Bot {
  const bot = new Bot(token);

  bot.command("start", async (ctx) => {
    service.player(ownerId(ctx), displayName(ctx));
    await ctx.reply("🎣 Welcome to Lake Ontario, angler. Type /fish to open your tackle box and start your collection.");
  });
  bot.command("fish", async (ctx) => sendHome(ctx, service));
  bot.command("fishing", async (ctx) => sendHome(ctx, service));
  bot.command("gear", async (ctx) => sendGear(ctx, service));
  bot.command("collection", async (ctx) => sendCollection(ctx, service));

  bot.on("callback_query:data", async (ctx) => {
    const parsed = parseCallback(ctx.callbackQuery.data);
    if (!parsed) {
      await ctx.answerCallbackQuery({ text: "That tackle command drifted away." });
      return;
    }
    if (parsed.ownerId !== ownerId(ctx)) {
      await ctx.answerCallbackQuery({ text: "This tackle box belongs to another angler.", show_alert: true });
      return;
    }
    await ctx.answerCallbackQuery();

    if (parsed.action === "home") return editPanel(ctx, homeCaption(service, ctx), homeKeyboard(ownerId(ctx)));
    if (parsed.action === "gear") return editPanel(ctx, gearCaption(service, ctx), gearKeyboard(service, ctx));
    if (parsed.action === "shop") return sendShop(ctx, service);
    if (parsed.action === "art" && parsed.kind) {
      await ctx.replyWithPhoto(new InputFile(equipmentArtPath(parsed.kind)), {
        caption: gearCaption(service, ctx),
        parse_mode: "Markdown",
        reply_markup: gearKeyboard(service, ctx),
      });
      return;
    }
    if (parsed.action === "collection") return editPanel(ctx, collectionCaption(service, ctx), collectionKeyboard(service, ctx));
    if (parsed.action === "cast") return castLine(ctx, service);
    if (parsed.action === "repair") {
      const result = service.repair(ownerId(ctx), displayName(ctx));
      return editPanel(ctx, `${result.ok ? "✅" : "⚠️"} ${result.message}\n\n${gearCaption(service, ctx)}`, gearKeyboard(service, ctx));
    }
    if (parsed.action === "sellall") {
      const result = service.sellAll(ownerId(ctx), displayName(ctx));
      return editPanel(ctx, `${result.ok ? "✅" : "⚠️"} ${result.message}\n\n${collectionCaption(service, ctx)}`, collectionKeyboard(service, ctx));
    }
    if (parsed.action === "sell") {
      const result = service.sell(ownerId(ctx), displayName(ctx), parsed.id ?? "");
      return editPanel(ctx, `${result.ok ? "✅" : "⚠️"} ${result.message}\n\n${collectionCaption(service, ctx)}`, collectionKeyboard(service, ctx));
    }
    if (!parsed.kind || !parsed.id) return;
    if (parsed.action === "buy") {
      const result = service.buy(ownerId(ctx), displayName(ctx), parsed.kind, parsed.id);
      return editPanel(ctx, `${result.ok ? "✅" : "⚠️"} ${result.message}\n\n${gearCaption(service, ctx)}`, gearKeyboard(service, ctx));
    }
    if (parsed.action === "equip") {
      const result = service.equip(ownerId(ctx), displayName(ctx), { [parsed.kind]: parsed.id } as { rod?: RodId; lure?: LureId; bait?: BaitId });
      return editPanel(ctx, `${result.ok ? "✅" : "⚠️"} ${result.message}\n\n${gearCaption(service, ctx)}`, gearKeyboard(service, ctx));
    }
  });

  return bot;
}
