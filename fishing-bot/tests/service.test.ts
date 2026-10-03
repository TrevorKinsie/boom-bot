import { strict as assert } from "node:assert";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { FishingService } from "../src/service.js";
import { FishingStore } from "../src/store.js";

function withStore(run: (filePath: string) => void): void {
  const directory = mkdtempSync(join(tmpdir(), "boom-fishing-"));
  try {
    run(join(directory, "fishing.json"));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test("a successful cast consumes bait, records a weighted fish, and survives reload", () => {
  withStore((filePath) => {
    const rolls = [0, 0, 0.5];
    const service = new FishingService(new FishingStore(filePath), () => rolls.shift() ?? 0);
    const result = service.cast("42", "Kevin");

    assert.equal(result.kind, "caught");
    if (result.kind !== "caught") return;
    assert.equal(result.species.id, "yellow-perch");
    assert.equal(result.fish.weightKg, 0.66);
    assert.equal(service.player("42", "Kevin").bait.nightcrawler, 15);
    assert.equal(service.player("42", "Kevin").catches.length, 1);

    const sale = service.sell("42", "Kevin", result.fish.id);
    assert.equal(sale.ok, true);
    assert.equal(service.player("42", "Kevin").gold, 172);

    const reloaded = new FishingService(new FishingStore(filePath));
    assert.equal(reloaded.player("42", "Kevin").catches.length, 0);
    assert.equal(reloaded.player("42", "Kevin").gold, 172);
  });
});

test("gear, lure, and bait purchases become a persistent collection", () => {
  withStore((filePath) => {
    const service = new FishingService(new FishingStore(filePath));
    const player = service.player("7", "Angler");
    player.gold = 1_000;

    assert.equal(service.buy("7", "Angler", "bait", "nightcrawler").ok, true);
    assert.equal(service.player("7", "Angler").bait.nightcrawler, 24);
    assert.equal(service.buy("7", "Angler", "rod", "bassline-graphite").ok, true);
    assert.equal(service.buy("7", "Angler", "lure", "silver-spoon").ok, true);
    assert.equal(service.buy("7", "Angler", "bait", "emerald-leech").ok, true);
    assert.equal(service.equip("7", "Angler", { rod: "bassline-graphite", lure: "silver-spoon", bait: "emerald-leech" }).ok, true);

    const saved = new FishingStore(filePath).getOrCreate("7", "Angler");
    assert.equal(saved.rods["bassline-graphite"].owned, true);
    assert.equal(saved.lures["silver-spoon"], true);
    assert.equal(saved.bait["emerald-leech"], 5);
    assert.deepEqual(saved.equipped, { rod: "bassline-graphite", lure: "silver-spoon", bait: "emerald-leech" });
  });
});

test("a trophy miss can break the equipped rod", () => {
  withStore((filePath) => {
    const rolls = [0.999999, 0.999999, 0];
    const service = new FishingService(new FishingStore(filePath), () => rolls.shift() ?? 0);
    const player = service.player("9", "Big Game Angler");
    player.bait["moon-moth"] = 1;
    player.equipped.bait = "moon-moth";

    const result = service.cast("9", "Big Game Angler");
    assert.equal(result.kind, "broken");
    if (result.kind !== "broken") return;
    assert.equal(result.species.id, "lake-sturgeon");
    assert.equal(service.player("9", "Big Game Angler").rods["cedar-reed"].condition, 0);
    assert.equal(service.player("9", "Big Game Angler").bait["moon-moth"], 0);
  });
});

test("broken rods block casting until they are repaired", () => {
  withStore((filePath) => {
    const service = new FishingService(new FishingStore(filePath));
    const player = service.player("10", "Repair Crew");
    player.rods["cedar-reed"].condition = 0;

    assert.equal(service.cast("10", "Repair Crew").kind, "rod_broken");
    player.gold = 100;
    assert.equal(service.repair("10", "Repair Crew").ok, true);
    assert.equal(service.player("10", "Repair Crew").rods["cedar-reed"].condition, 100);
  });
});

test("failed multi-item equip is atomic", () => {
  withStore((filePath) => {
    const service = new FishingService(new FishingStore(filePath));
    const player = service.player("11", "Atomic Angler");
    player.gold = 1_000;
    assert.equal(service.buy("11", "Atomic Angler", "rod", "bassline-graphite").ok, true);
    assert.equal(service.buy("11", "Atomic Angler", "lure", "silver-spoon").ok, true);

    const before = { ...service.player("11", "Atomic Angler").equipped };
    const failed = service.equip("11", "Atomic Angler", {
      rod: "bassline-graphite",
      lure: "marsh-frog",
    });
    assert.equal(failed.ok, false);
    assert.deepEqual(service.player("11", "Atomic Angler").equipped, before);
    assert.deepEqual(new FishingStore(filePath).getOrCreate("11", "Atomic Angler").equipped, before);
  });
});

test("malformed persisted players are repaired before the next cast", () => {
  withStore((filePath) => {
    writeFileSync(filePath, JSON.stringify({
      version: 1,
      players: {
        "12": {
          displayName: "Recovered Angler",
          gold: -50,
          rods: { "cedar-reed": { owned: true, condition: 999 } },
          equipped: { rod: "stormglass", bait: "moon-moth" },
          catches: [{ id: "bad", speciesId: "not-a-fish", weightKg: 5, value: 1, caughtAt: "now" }],
        },
      },
    }));

    const service = new FishingService(new FishingStore(filePath));
    const player = service.player("12", "Recovered Angler");
    assert.equal(player.gold, 0);
    assert.equal(player.rods["cedar-reed"].condition, 100);
    assert.equal(player.equipped.rod, "cedar-reed");
    assert.equal(player.equipped.bait, "nightcrawler");
    assert.equal(player.catches.length, 0);
    assert.doesNotThrow(() => service.cast("12", "Recovered Angler"));
  });
});

test("a failed save rolls a fishing action back in memory", () => {
  withStore((filePath) => {
    const store = new FishingStore(filePath);
    const service = new FishingService(store, () => 0);
    const player = service.player("13", "Rollback Angler");
    const before = structuredClone(player);
    store.save = () => {
      throw new Error("disk full");
    };

    assert.throws(() => service.cast("13", "Rollback Angler"), /disk full/);
    assert.deepEqual(player, before);
  });
});
