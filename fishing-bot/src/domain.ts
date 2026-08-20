export type RodId = "cedar-reed" | "bassline-graphite" | "stormglass";
export type LureId = "scarlet-bobber" | "silver-spoon" | "marsh-frog";
export type BaitId = "nightcrawler" | "emerald-leech" | "moon-moth" | "corn-dough";

export interface RodDefinition {
  id: RodId;
  name: string;
  tier: number;
  price: number;
  catchBonus: number;
  breakMultiplier: number;
  description: string;
}

export interface LureDefinition {
  id: LureId;
  name: string;
  tier: number;
  price: number;
  catchBonus: number;
  rareBias: number;
  description: string;
}

export interface BaitDefinition {
  id: BaitId;
  name: string;
  tier: number;
  packSize: number;
  price: number;
  catchBonus: number;
  rareBias: number;
  description: string;
}

export interface FishSpecies {
  id: string;
  name: string;
  scientificName: string;
  emoji: string;
  tier: number;
  minBaitTier: number;
  baseWeightKg: [number, number];
  catchChance: number;
  breakChance: number;
  goldPerKg: number;
  wikipediaPage: string;
  fallbackImageUrl: string;
}

export interface RodInventory {
  owned: boolean;
  condition: number;
}

export interface FishCatch {
  id: string;
  speciesId: string;
  weightKg: number;
  value: number;
  caughtAt: string;
}

export interface EquippedGear {
  rod: RodId;
  lure: LureId;
  bait: BaitId;
}

export interface PlayerState {
  userId: string;
  displayName: string;
  gold: number;
  rods: Record<RodId, RodInventory>;
  lures: Record<LureId, boolean>;
  bait: Record<BaitId, number>;
  equipped: EquippedGear;
  catches: FishCatch[];
  totalCasts: number;
  totalFish: number;
  biggestFishKg: number;
}

export type CastResult =
  | { kind: "caught"; fish: FishCatch; species: FishSpecies; rod: RodDefinition; bait: BaitDefinition; lure: LureDefinition }
  | { kind: "missed"; species: FishSpecies; rod: RodDefinition; bait: BaitDefinition; lure: LureDefinition }
  | { kind: "broken"; species: FishSpecies; rod: RodDefinition; bait: BaitDefinition; lure: LureDefinition }
  | { kind: "no_bait"; bait: BaitDefinition }
  | { kind: "rod_broken"; rod: RodDefinition };

export const RODS: Record<RodId, RodDefinition> = {
  "cedar-reed": {
    id: "cedar-reed",
    name: "Cedar Reed",
    tier: 1,
    price: 0,
    catchBonus: 0.01,
    breakMultiplier: 1,
    description: "A forgiving hand-built rod for dockside panfish.",
  },
  "bassline-graphite": {
    id: "bassline-graphite",
    name: "Bassline Graphite",
    tier: 2,
    price: 180,
    catchBonus: 0.09,
    breakMultiplier: 0.78,
    description: "Sensitive enough to feel a walleye breathe on the line.",
  },
  stormglass: {
    id: "stormglass",
    name: "Stormglass Trophy",
    tier: 3,
    price: 720,
    catchBonus: 0.16,
    breakMultiplier: 0.55,
    description: "A ridiculous glass-and-brass rig for ridiculous fish.",
  },
};

export const LURES: Record<LureId, LureDefinition> = {
  "scarlet-bobber": {
    id: "scarlet-bobber",
    name: "Scarlet Bobber",
    tier: 1,
    price: 0,
    catchBonus: 0.03,
    rareBias: 0,
    description: "Bright, buoyant, and impossible to lose in a calm bay.",
  },
  "silver-spoon": {
    id: "silver-spoon",
    name: "Silver Spoon",
    tier: 2,
    price: 90,
    catchBonus: 0.08,
    rareBias: 0.14,
    description: "Flashes like a smelt when the sun finds the chop.",
  },
  "marsh-frog": {
    id: "marsh-frog",
    name: "Marshlight Frog",
    tier: 3,
    price: 260,
    catchBonus: 0.12,
    rareBias: 0.25,
    description: "A hand-painted topwater troublemaker for ambush predators.",
  },
};

export const BAIT: Record<BaitId, BaitDefinition> = {
  nightcrawler: {
    id: "nightcrawler",
    name: "Nightcrawlers",
    tier: 1,
    packSize: 8,
    price: 18,
    catchBonus: 0.05,
    rareBias: 0,
    description: "The honest workhorse of every Ontario tackle box.",
  },
  "emerald-leech": {
    id: "emerald-leech",
    name: "Emerald Leeches",
    tier: 2,
    packSize: 5,
    price: 42,
    catchBonus: 0.1,
    rareBias: 0.12,
    description: "A wriggling invitation for bass, walleye, and trout.",
  },
  "moon-moth": {
    id: "moon-moth",
    name: "Moon-Moth Larvae",
    tier: 3,
    packSize: 3,
    price: 88,
    catchBonus: 0.15,
    rareBias: 0.26,
    description: "Glows just enough to make trophy fish curious after dusk.",
  },
  "corn-dough": {
    id: "corn-dough",
    name: "Corn-Dough Bait",
    tier: 1,
    packSize: 8,
    price: 12,
    catchBonus: 0.03,
    rareBias: 0,
    description: "Sweet, sticky, and suspiciously effective near warm marinas.",
  },
};

export const FISH: FishSpecies[] = [
  {
    id: "yellow-perch",
    name: "Yellow Perch",
    scientificName: "Perca flavescens",
    emoji: "🐟",
    tier: 1,
    minBaitTier: 1,
    baseWeightKg: [0.12, 1.2],
    catchChance: 0.88,
    breakChance: 0.01,
    goldPerKg: 34,
    wikipediaPage: "Yellow perch",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Perca_flavescens.jpg",
  },
  {
    id: "rock-bass",
    name: "Rock Bass",
    scientificName: "Ambloplites rupestris",
    emoji: "🐠",
    tier: 1,
    minBaitTier: 1,
    baseWeightKg: [0.15, 0.55],
    catchChance: 0.84,
    breakChance: 0.012,
    goldPerKg: 42,
    wikipediaPage: "Rock bass",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Ambloplites_rupestris.jpg",
  },
  {
    id: "smallmouth-bass",
    name: "Smallmouth Bass",
    scientificName: "Micropterus dolomieu",
    emoji: "🐟",
    tier: 2,
    minBaitTier: 1,
    baseWeightKg: [0.35, 3.2],
    catchChance: 0.68,
    breakChance: 0.035,
    goldPerKg: 64,
    wikipediaPage: "Smallmouth bass",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Smallmouth_bass.jpg",
  },
  {
    id: "largemouth-bass",
    name: "Largemouth Bass",
    scientificName: "Micropterus salmoides",
    emoji: "🐟",
    tier: 2,
    minBaitTier: 1,
    baseWeightKg: [0.4, 4.5],
    catchChance: 0.58,
    breakChance: 0.045,
    goldPerKg: 72,
    wikipediaPage: "Largemouth bass",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Largemouth_bass.jpg",
  },
  {
    id: "walleye",
    name: "Walleye",
    scientificName: "Sander vitreus",
    emoji: "✨",
    tier: 3,
    minBaitTier: 2,
    baseWeightKg: [0.8, 8.5],
    catchChance: 0.43,
    breakChance: 0.09,
    goldPerKg: 105,
    wikipediaPage: "Walleye",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Walleye.jpg",
  },
  {
    id: "northern-pike",
    name: "Northern Pike",
    scientificName: "Esox lucius",
    emoji: "🦈",
    tier: 3,
    minBaitTier: 2,
    baseWeightKg: [1.1, 12],
    catchChance: 0.34,
    breakChance: 0.13,
    goldPerKg: 116,
    wikipediaPage: "Northern pike",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Esox_lucius.jpg",
  },
  {
    id: "lake-trout",
    name: "Lake Trout",
    scientificName: "Salvelinus namaycush",
    emoji: "❄️",
    tier: 3,
    minBaitTier: 2,
    baseWeightKg: [1.5, 15],
    catchChance: 0.29,
    breakChance: 0.14,
    goldPerKg: 128,
    wikipediaPage: "Lake trout",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Salvelinus_namaycush.jpg",
  },
  {
    id: "coho-salmon",
    name: "Coho Salmon",
    scientificName: "Oncorhynchus kisutch",
    emoji: "🌊",
    tier: 4,
    minBaitTier: 3,
    baseWeightKg: [2, 10],
    catchChance: 0.22,
    breakChance: 0.18,
    goldPerKg: 155,
    wikipediaPage: "Coho salmon",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Coho_salmon.jpg",
  },
  {
    id: "chinook-salmon",
    name: "Chinook Salmon",
    scientificName: "Oncorhynchus tshawytscha",
    emoji: "👑",
    tier: 4,
    minBaitTier: 3,
    baseWeightKg: [3, 22],
    catchChance: 0.16,
    breakChance: 0.23,
    goldPerKg: 185,
    wikipediaPage: "Chinook salmon",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Chinook_salmon.jpg",
  },
  {
    id: "lake-sturgeon",
    name: "Lake Sturgeon",
    scientificName: "Acipenser fulvescens",
    emoji: "🐉",
    tier: 5,
    minBaitTier: 3,
    baseWeightKg: [5, 108],
    catchChance: 0.08,
    breakChance: 0.36,
    goldPerKg: 260,
    wikipediaPage: "Lake sturgeon",
    fallbackImageUrl: "https://en.wikipedia.org/wiki/Special:FilePath/Lake_sturgeon.jpg",
  },
];

export const ROD_LIST = Object.values(RODS);
export const LURE_LIST = Object.values(LURES);
export const BAIT_LIST = Object.values(BAIT);

export function fishById(id: string): FishSpecies {
  const fish = FISH.find((candidate) => candidate.id === id);
  if (!fish) throw new Error(`Unknown fish: ${id}`);
  return fish;
}

export function createDefaultPlayer(userId: string, displayName: string): PlayerState {
  return {
    userId,
    displayName: displayName || "Angler",
    gold: 150,
    rods: {
      "cedar-reed": { owned: true, condition: 100 },
      "bassline-graphite": { owned: false, condition: 100 },
      stormglass: { owned: false, condition: 100 },
    },
    lures: {
      "scarlet-bobber": true,
      "silver-spoon": false,
      "marsh-frog": false,
    },
    bait: {
      nightcrawler: 16,
      "emerald-leech": 0,
      "moon-moth": 0,
      "corn-dough": 8,
    },
    equipped: {
      rod: "cedar-reed",
      lure: "scarlet-bobber",
      bait: "nightcrawler",
    },
    catches: [],
    totalCasts: 0,
    totalFish: 0,
    biggestFishKg: 0,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function nonNegativeInteger(value: unknown, fallback: number): number {
  return Math.max(0, Math.floor(finiteNumber(value, fallback)));
}

function isRodId(value: unknown): value is RodId {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(RODS, value);
}

function isLureId(value: unknown): value is LureId {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(LURES, value);
}

function isBaitId(value: unknown): value is BaitId {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(BAIT, value);
}

/** Turn persisted or otherwise untrusted data into a complete playable state. */
export function normalizePlayer(raw: unknown, userId: string, displayName: string): PlayerState {
  const defaults = createDefaultPlayer(userId, displayName);
  if (!isRecord(raw)) return defaults;

  const savedRods = isRecord(raw.rods) ? raw.rods : {};
  const rods = { ...defaults.rods };
  for (const rod of ROD_LIST) {
    const candidate = savedRods[rod.id];
    const saved = isRecord(candidate) ? candidate : undefined;
    if (!saved) continue;
    rods[rod.id] = {
      owned: typeof saved.owned === "boolean" ? saved.owned : defaults.rods[rod.id].owned,
      condition: Math.round(clamp(finiteNumber(saved.condition, defaults.rods[rod.id].condition), 0, 100)),
    };
  }

  const savedLures = isRecord(raw.lures) ? raw.lures : {};
  const lures = { ...defaults.lures };
  for (const lure of LURE_LIST) {
    if (typeof savedLures[lure.id] === "boolean") lures[lure.id] = savedLures[lure.id] as boolean;
  }

  const savedBait = isRecord(raw.bait) ? raw.bait : {};
  const bait = { ...defaults.bait };
  for (const baitDefinition of BAIT_LIST) {
    bait[baitDefinition.id] = nonNegativeInteger(savedBait[baitDefinition.id], defaults.bait[baitDefinition.id]);
  }

  const savedEquipped = isRecord(raw.equipped) ? raw.equipped : {};
  const equipped: EquippedGear = {
    rod: isRodId(savedEquipped.rod) && rods[savedEquipped.rod].owned
      ? savedEquipped.rod
      : defaults.equipped.rod,
    lure: isLureId(savedEquipped.lure) && lures[savedEquipped.lure]
      ? savedEquipped.lure
      : defaults.equipped.lure,
    bait: isBaitId(savedEquipped.bait) && bait[savedEquipped.bait] > 0
      ? savedEquipped.bait
      : defaults.equipped.bait,
  };

  const catches: FishCatch[] = [];
  const catchIds = new Set<string>();
  if (Array.isArray(raw.catches)) {
    for (const rawCatch of raw.catches) {
      if (!isRecord(rawCatch) || typeof rawCatch.id !== "string" || catchIds.has(rawCatch.id)) continue;
      const speciesId = typeof rawCatch.speciesId === "string" ? rawCatch.speciesId : "";
      if (!FISH.some((species) => species.id === speciesId)) continue;
      const weightKg = finiteNumber(rawCatch.weightKg, -1);
      const value = finiteNumber(rawCatch.value, -1);
      if (weightKg <= 0 || value < 0 || typeof rawCatch.caughtAt !== "string") continue;
      catchIds.add(rawCatch.id);
      catches.push({
        id: rawCatch.id,
        speciesId,
        weightKg,
        value: Math.max(0, Math.round(value)),
        caughtAt: rawCatch.caughtAt,
      });
    }
  }

  const savedDisplayName = typeof raw.displayName === "string" && raw.displayName.length > 0
    ? raw.displayName.replace(/\s+/g, " ").trim().slice(0, 64)
    : displayName;
  const biggestCatch = catches.reduce((largest, fish) => Math.max(largest, fish.weightKg), 0);
  return {
    userId,
    displayName: savedDisplayName || "Angler",
    gold: nonNegativeInteger(raw.gold, defaults.gold),
    rods,
    lures,
    bait,
    equipped,
    catches,
    totalCasts: Math.max(nonNegativeInteger(raw.totalCasts, 0), catches.length),
    totalFish: Math.max(nonNegativeInteger(raw.totalFish, 0), catches.length),
    biggestFishKg: Math.max(0, finiteNumber(raw.biggestFishKg, 0), biggestCatch),
  };
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function formatWeight(weightKg: number): string {
  return `${weightKg.toFixed(weightKg >= 10 ? 1 : 2)} kg`;
}
