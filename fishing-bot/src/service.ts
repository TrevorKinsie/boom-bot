import {
  BAIT,
  BaitDefinition,
  BaitId,
  CastResult,
  clamp,
  EquippedGear,
  FISH,
  FishSpecies,
  FishCatch,
  LURE_LIST,
  LURES,
  LureDefinition,
  LureId,
  PlayerState,
  ROD_LIST,
  RODS,
  RodDefinition,
  RodId,
} from "./domain.js";
import { FishingStore } from "./store.js";
import { randomUUID } from "node:crypto";

export interface PurchaseResult {
  ok: boolean;
  message: string;
}

export class FishingService {
  private readonly store: FishingStore;
  private readonly random: () => number;

  public constructor(store: FishingStore, random: () => number = Math.random) {
    this.store = store;
    this.random = random;
  }

  public player(userId: string, displayName: string): PlayerState {
    return this.store.getOrCreate(userId, displayName);
  }

  public cast(userId: string, displayName: string): CastResult {
    const player = this.player(userId, displayName);
    const before = structuredClone(player);
    const rod = RODS[player.equipped.rod];
    const bait = BAIT[player.equipped.bait];
    const lure = LURES[player.equipped.lure];

    if (player.bait[bait.id] <= 0) return { kind: "no_bait", bait };
    if (!player.rods[rod.id].owned || player.rods[rod.id].condition <= 0) {
      return { kind: "rod_broken", rod };
    }

    player.bait[bait.id] -= 1;
    player.totalCasts += 1;

    const eligible = FISH.filter((fish) => fish.minBaitTier <= bait.tier);
    const species = this.weightedFish(eligible, bait, lure);
    const hookChance = clamp(
      species.catchChance + rod.catchBonus + bait.catchBonus + lure.catchBonus - Math.max(0, species.tier - bait.tier) * 0.04,
      0.04,
      0.97,
    );

    if (this.nextRandom() > hookChance) {
      const breakChance = species.breakChance * rod.breakMultiplier * (1 - bait.rareBias * 0.12);
      if (species.tier >= 3 && this.nextRandom() < breakChance) {
        player.rods[rod.id].condition = 0;
        this.saveWithRollback(player, before);
        return { kind: "broken", species, rod, bait, lure };
      }
      this.saveWithRollback(player, before);
      return { kind: "missed", species, rod, bait, lure };
    }

    const [minWeight, maxWeight] = species.baseWeightKg;
    const weightKg = Number((minWeight + this.nextRandom() * (maxWeight - minWeight)).toFixed(2));
    const value = Math.max(1, Math.round(weightKg * species.goldPerKg));
    const fish: FishCatch = {
      id: randomUUID(),
      speciesId: species.id,
      weightKg,
      value,
      caughtAt: new Date().toISOString(),
    };
    player.catches.unshift(fish);
    player.totalFish += 1;
    player.biggestFishKg = Math.max(player.biggestFishKg, weightKg);
    this.saveWithRollback(player, before);
    return { kind: "caught", fish, species, rod, bait, lure };
  }

  public equip(userId: string, displayName: string, gear: Partial<EquippedGear>): PurchaseResult {
    const player = this.player(userId, displayName);
    const before = structuredClone(player);
    if (gear.rod) {
      if (!RODS[gear.rod] || !player.rods[gear.rod]?.owned) return { ok: false, message: "You do not own that rod yet." };
    }
    if (gear.lure) {
      if (!LURES[gear.lure] || !player.lures[gear.lure]) return { ok: false, message: "You do not own that lure yet." };
    }
    if (gear.bait) {
      if (!BAIT[gear.bait] || (player.bait[gear.bait] ?? 0) <= 0) return { ok: false, message: "You are out of that bait." };
    }
    if (!gear.rod && !gear.lure && !gear.bait) return { ok: false, message: "Choose a piece of tackle to equip." };
    if (gear.rod) player.equipped.rod = gear.rod;
    if (gear.lure) player.equipped.lure = gear.lure;
    if (gear.bait) player.equipped.bait = gear.bait;
    this.saveWithRollback(player, before);
    return { ok: true, message: "Tackle equipped." };
  }

  public buy(userId: string, displayName: string, kind: "rod" | "lure" | "bait", id: string): PurchaseResult {
    const player = this.player(userId, displayName);
    const before = structuredClone(player);
    if (kind === "rod") {
      const rod = RODS[id as RodId];
      if (!rod) return { ok: false, message: "That rod slipped off the catalog." };
      if (player.rods[rod.id].owned) return { ok: false, message: "You already own that rod." };
      if (!this.spend(player, rod.price)) return { ok: false, message: `You need ${rod.price} gold for ${rod.name}.` };
      player.rods[rod.id] = { owned: true, condition: 100 };
      this.saveWithRollback(player, before);
      return { ok: true, message: `${rod.name} added to your collection.` };
    }
    if (kind === "lure") {
      const lure = LURES[id as LureId];
      if (!lure) return { ok: false, message: "That lure slipped off the catalog." };
      if (player.lures[lure.id]) return { ok: false, message: "You already own that lure." };
      if (!this.spend(player, lure.price)) return { ok: false, message: `You need ${lure.price} gold for ${lure.name}.` };
      player.lures[lure.id] = true;
      this.saveWithRollback(player, before);
      return { ok: true, message: `${lure.name} added to your collection.` };
    }

    const bait = BAIT[id as BaitId];
    if (!bait) return { ok: false, message: "That bait slipped off the catalog." };
    if (!this.spend(player, bait.price)) return { ok: false, message: `You need ${bait.price} gold for a pack of ${bait.name}.` };
    player.bait[bait.id] += bait.packSize;
    this.saveWithRollback(player, before);
    return { ok: true, message: `Bought ${bait.packSize} ${bait.name}.` };
  }

  public repair(userId: string, displayName: string): PurchaseResult {
    const player = this.player(userId, displayName);
    const before = structuredClone(player);
    const rod = RODS[player.equipped.rod];
    const cost = rod.tier * 24;
    if (player.rods[rod.id].condition > 0) return { ok: false, message: `${rod.name} is still in one piece.` };
    if (!this.spend(player, cost)) return { ok: false, message: `You need ${cost} gold to repair ${rod.name}.` };
    player.rods[rod.id].condition = 100;
    this.saveWithRollback(player, before);
    return { ok: true, message: `${rod.name} has been lovingly reassembled.` };
  }

  public sell(userId: string, displayName: string, catchId: string): PurchaseResult {
    const player = this.player(userId, displayName);
    const before = structuredClone(player);
    const index = player.catches.findIndex((fish) => fish.id === catchId);
    if (index < 0) return { ok: false, message: "That fish has already escaped your ledger." };
    const [fish] = player.catches.splice(index, 1);
    player.gold += fish.value;
    this.saveWithRollback(player, before);
    return { ok: true, message: `Sold ${this.fishName(fish)} for ${fish.value} gold.` };
  }

  public sellAll(userId: string, displayName: string): PurchaseResult {
    const player = this.player(userId, displayName);
    const before = structuredClone(player);
    if (player.catches.length === 0) return { ok: false, message: "Your livewell is already empty." };
    const value = player.catches.reduce((total, fish) => total + fish.value, 0);
    const count = player.catches.length;
    player.catches = [];
    player.gold += value;
    this.saveWithRollback(player, before);
    return { ok: true, message: `Sold ${count} fish for ${value} gold.` };
  }

  private weightedFish(eligible: FishSpecies[], bait: BaitDefinition, lure: LureDefinition): FishSpecies {
    const weighted = eligible.map((fish) => ({
      fish,
      weight: Math.max(0.01, 1 / fish.tier) * fish.catchChance * (1 + (bait.rareBias + lure.rareBias) * fish.tier),
    }));
    const total = weighted.reduce((sum, item) => sum + item.weight, 0);
    let target = this.nextRandom() * total;
    for (const item of weighted) {
      target -= item.weight;
      if (target <= 0) return item.fish;
    }
    return weighted[weighted.length - 1].fish;
  }

  private fishName(fish: FishCatch): string {
    return FISH.find((species) => species.id === fish.speciesId)?.name ?? "mystery fish";
  }

  private spend(player: PlayerState, amount: number): boolean {
    if (player.gold < amount) return false;
    player.gold -= amount;
    return true;
  }

  private nextRandom(): number {
    const value = this.random();
    return Number.isFinite(value) ? clamp(value, 0, 0.999999999) : 0.5;
  }

  private saveWithRollback(player: PlayerState, before: PlayerState): void {
    try {
      this.store.save();
    } catch (error) {
      Object.assign(player, before);
      throw error;
    }
  }
}

export function gearFor(player: PlayerState): {
  rod: RodDefinition;
  lure: LureDefinition;
  bait: BaitDefinition;
} {
  return {
    rod: RODS[player.equipped.rod],
    lure: LURES[player.equipped.lure],
    bait: BAIT[player.equipped.bait],
  };
}

export function collectionSummary(player: PlayerState): Array<{ species: FishSpecies; count: number; totalWeightKg: number }> {
  return FISH.map((species) => {
    const catches = player.catches.filter((fish) => fish.speciesId === species.id);
    return {
      species,
      count: catches.length,
      totalWeightKg: catches.reduce((total, fish) => total + fish.weightKg, 0),
    };
  }).filter((entry) => entry.count > 0);
}

export function catalogCounts(player: PlayerState): { rods: number; lures: number; bait: number } {
  return {
    rods: ROD_LIST.filter((rod) => player.rods[rod.id].owned).length,
    lures: LURE_LIST.filter((lure) => player.lures[lure.id]).length,
    bait: Object.values(player.bait).reduce((total, count) => total + count, 0),
  };
}
