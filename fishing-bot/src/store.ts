import { dirname } from "node:path";
import { randomUUID } from "node:crypto";
import { closeSync, fsyncSync, mkdirSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";

import { createDefaultPlayer, normalizePlayer, PlayerState } from "./domain.js";

interface StoreFile {
  version: 1;
  players: Record<string, PlayerState>;
}

export class FishingStore {
  private readonly filePath: string;
  private readonly data: StoreFile;

  public constructor(filePath: string) {
    this.filePath = filePath;
    this.data = this.load();
  }

  public getOrCreate(userId: string, displayName: string): PlayerState {
    const existing = this.data.players[userId];
    if (existing) {
      if (displayName && existing.displayName !== displayName) {
        const previousDisplayName = existing.displayName;
        existing.displayName = displayName;
        try {
          this.save();
        } catch (error) {
          existing.displayName = previousDisplayName;
          throw error;
        }
      }
      return existing;
    }

    const player = createDefaultPlayer(userId, displayName);
    this.data.players[userId] = player;
    try {
      this.save();
    } catch (error) {
      delete this.data.players[userId];
      throw error;
    }
    return player;
  }

  public save(): void {
    mkdirSync(dirname(this.filePath), { recursive: true });
    const temporaryPath = `${this.filePath}.${process.pid}.${randomUUID()}.tmp`;
    try {
      writeFileSync(temporaryPath, `${JSON.stringify(this.data, null, 2)}\n`, {
        encoding: "utf8",
        mode: 0o600,
      });
      const fd = openSync(temporaryPath, "r");
      try {
        fsyncSync(fd);
      } finally {
        closeSync(fd);
      }
      renameSync(temporaryPath, this.filePath);
    } catch (error) {
      try {
        unlinkSync(temporaryPath);
      } catch {
        // Preserve the original write/rename error.
      }
      throw error;
    }
  }

  private load(): StoreFile {
    try {
      const parsed = JSON.parse(readFileSync(this.filePath, "utf8")) as unknown;
      if (
        typeof parsed === "object" &&
        parsed !== null &&
        !Array.isArray(parsed) &&
        "version" in parsed &&
        parsed.version === 1 &&
        "players" in parsed &&
        typeof parsed.players === "object" &&
        parsed.players !== null &&
        !Array.isArray(parsed.players)
      ) {
        const players = Object.create(null) as Record<string, PlayerState>;
        for (const [userId, rawPlayer] of Object.entries(parsed.players)) {
          players[userId] = normalizePlayer(rawPlayer, userId, "Angler");
        }
        return { version: 1, players };
      }
    } catch {
      // A first run, an empty mounted volume, or a partial old file all start cleanly.
    }
    return { version: 1, players: Object.create(null) as Record<string, PlayerState> };
  }
}
