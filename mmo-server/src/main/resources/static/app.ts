/* Boom Bot MMO — low-poly browser client (Three.js r128).
 * TypeScript source; compiled to plain JS by `tsc` (see build.sh). */
"use strict";

const SERVER = "";
const WALLET_TOKEN = "mmo-token";
const WALLET_NAME = "mmo-name";

// ---- persistence ---------------------------------------------------------
interface KVStore {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
  removeItem(k: string): void;
}

const storage: KVStore = (() => {
  try {
    const s = window.localStorage;
    s.getItem("__probe__");
    return s;
  } catch (e) {
    const mem: Record<string, string> = {};
    return {
      getItem: (k) => (k in mem ? mem[k] : null),
      setItem: (k, v) => {
        mem[k] = String(v);
      },
      removeItem: (k) => {
        delete mem[k];
      },
    };
  }
})();

// ---- API payload types ---------------------------------------------------
interface WorldSnap {
  w: number;
  h: number;
  spawn: { x: number; y: number };
  bank: { x: number; y: number };
  tiles: number[];
}

interface ResourceSnap {
  id: string;
  type: "tree" | "rock";
  x: number;
  y: number;
  amount: number;
  maxAmount: number;
  alive: boolean;
}

interface PlayerSnap {
  id: string;
  name: string;
  x: number;
  y: number;
  moving: boolean;
  miningLevel: number;
  woodcuttingLevel: number;
}

interface SelfSnap extends PlayerSnap {
  hp: number;
  maxHp: number;
  goldCents: number;
  walletCents: number;
  inventory: Record<string, number>;
  bank: Record<string, number>;
  miningXp: number;
  woodcuttingXp: number;
  gathering: string | null;
}

interface GameSnap {
  you: SelfSnap | null;
  t: number;
  players: PlayerSnap[];
  resources: ResourceSnap[];
}

interface JoinResp {
  ok: boolean;
  id: string;
  name: string;
  token: string;
}

// ---- state -------------------------------------------------------------
interface AppState {
  token: string | null;
  name: string | null;
  world: WorldSnap | null;
  you: SelfSnap | null;
  players: Map<string, PlayerSnap>;
  playerTweens: Map<string, { x: number; y: number }>;
  resources: Map<string, ResourceSnap>;
  resourceObjs: Map<string, THREE.Object3D>;
  playerObjs: Map<string, THREE.Object3D>;
  online: number;
}

const state: AppState = {
  token: storage.getItem(WALLET_TOKEN),
  name: storage.getItem(WALLET_NAME),
  world: null,
  you: null,
  players: new Map(),
  playerTweens: new Map(),
  resources: new Map(),
  resourceObjs: new Map(),
  playerObjs: new Map(),
  online: 0,
};

let myId: string | null = null;
let gatherBusy = false;

// ---- api ---------------------------------------------------------------
async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(SERVER + path, opts);
  let j: unknown = {};
  try {
    j = await r.json();
  } catch (e) {
    /* ignore */
  }
  if (!r.ok) {
    const msg = (j as { error?: string }).error || "HTTP " + r.status;
    const err = Object.assign(new Error(msg), { status: r.status });
    throw err;
  }
  return j as T;
}

function post<T = Record<string, unknown>>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function money(n: number): string {
  return (n / 100).toFixed(2);
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function esc(s: string): string {
  return String(s).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c] ?? c);
}

function colorFor(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const hue = (h % 360) / 360;
  const c = new THREE.Color().setHSL(hue, 0.75, 0.55);
  return "#" + c.getHexString();
}

function el<T extends HTMLElement = HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error("Missing element #" + id);
  return node as T;
}

// ---- three.js core ------------------------------------------------------
let scene!: THREE.Scene;
let camera!: THREE.PerspectiveCamera;
let renderer!: THREE.WebGLRenderer;
let controls!: THREE.OrbitControls;

function initScene() {
  if (typeof THREE === "undefined") {
    throw new Error("three.js did not load");
  }
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x8fb6ef);
  scene.fog = new THREE.Fog(0x8fb6ef, 120, 260);

  camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    0.1,
    600,
  );
  camera.position.set(38, 62, 70);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = false;
  el("scene").appendChild(renderer.domElement);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(36, 0, 36);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI / 2.1;
  controls.update();

  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 0.85);
  sun.position.set(60, 90, 30);
  scene.add(sun);

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
}

function stdMat(color: string | number, opts?: THREE.MaterialOptions) {
  return new THREE.MeshLambertMaterial(
    Object.assign({ color, flatShading: true }, opts || {}),
  );
}

// ---- static world -------------------------------------------------------
let clickRaycaster!: THREE.Raycaster;
let groundPlane!: THREE.Plane;

function buildWorld(w: WorldSnap) {
  state.world = w;
  const W = w.w,
    H = w.h;
  clickRaycaster = new THREE.Raycaster();
  groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

  // Base grass.
  const grass = new THREE.Mesh(new THREE.PlaneGeometry(W, H), stdMat(0x79b64a));
  grass.rotation.x = -Math.PI / 2;
  grass.position.set(W / 2, -0.02, H / 2);
  scene.add(grass);

  // Water lake (tiles 1).
  let minX = W,
    minY = H,
    maxX = 0,
    maxY = 0,
    count = 0;
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      if (w.tiles[y * W + x] === 1) {
        minX = Math.min(minX, x);
        maxX = Math.max(maxX, x);
        minY = Math.min(minY, y);
        maxY = Math.max(maxY, y);
        count++;
      }
    }
  if (count > 0) {
    const ww = maxX - minX + 1,
      hh = maxY - minY + 1;
    const lake = new THREE.Mesh(
      new THREE.BoxGeometry(ww, 0.35, hh),
      stdMat(0x2e7cc9, { transparent: true, opacity: 0.88 }),
    );
    lake.position.set((minX + maxX + 1) / 2, -0.05, (minY + maxY + 1) / 2);
    scene.add(lake);
  }

  // Path (tiles 2) + bank footprint (tiles 4).
  const pathGeom = new THREE.BoxGeometry(1.02, 0.06, 1.02);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const t = w.tiles[y * W + x];
      if (t === 2) {
        const m = new THREE.Mesh(pathGeom, stdMat(0xc9a86b));
        m.position.set(x + 0.5, 0, y + 0.5);
        scene.add(m);
      } else if (t === 3) {
        // Decorative obstacle rock.
        const r = new THREE.Mesh(
          new THREE.IcosahedronGeometry(0.42, 1),
          stdMat(0x8b8e94),
        );
        r.position.set(x + 0.5, 0.3, y + 0.5);
        r.scale.y = 0.7 + (0.4 * ((x * 7 + y * 13) % 5)) / 5;
        r.rotation.y = (x * 1.7 + y) % Math.PI;
        scene.add(r);
      }
    }

  // Bank building at bank tiles.
  buildBank(w);
}

function buildBank(w: WorldSnap) {
  // House built roughly at the bank tile footprint.
  const bx = w.bank.x - 0.5,
    bz = w.bank.y - 0.5;
  const base = new THREE.Mesh(
    new THREE.BoxGeometry(3.4, 2.2, 3.4),
    stdMat(0xd8d2c0),
  );
  base.position.set(bx, 1.1, bz);
  scene.add(base);
  const roof = new THREE.Mesh(
    new THREE.ConeGeometry(2.9, 1.8, 4),
    stdMat(0x9a4b3f),
  );
  roof.rotation.y = Math.PI / 4;
  roof.position.set(bx, 2.6, bz);
  scene.add(roof);
  // Vault sign + coin pop.
  const sign = new THREE.Mesh(
    new THREE.BoxGeometry(1.4, 0.6, 0.2),
    stdMat(0xffcf5c),
  );
  sign.position.set(bx, 2.1, bz + 1.72);
  scene.add(sign);
  const gold = new THREE.Mesh(
    new THREE.CylinderGeometry(0.4, 0.4, 0.18, 12),
    stdMat(0xffcf5c),
  );
  gold.rotation.x = Math.PI / 2;
  gold.position.set(bx - 1.4, 0.12, bz + 1.5);
  scene.add(gold);
}

// ---- resource & player meshes ------------------------------------------
function makeResourceMesh(r: ResourceSnap): THREE.Object3D {
  let mesh: THREE.Object3D;
  if (r.type === "tree") {
    const g = new THREE.Group();
    const trunk = new THREE.Mesh(
      new THREE.BoxGeometry(0.35, 1.1, 0.35),
      stdMat(0x6b4a2b),
    );
    trunk.position.y = 0.55;
    const foliage = new THREE.Mesh(
      new THREE.ConeGeometry(1.0, 2.2, 7),
      stdMat(0x4f7a34),
    );
    foliage.position.y = 2.1;
    g.add(trunk);
    g.add(foliage);
    mesh = g;
  } else {
    mesh = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.85, 1),
      stdMat(0x777d86),
    );
    mesh.scale.y = 1.25;
  }
  mesh.position.set(r.x, r.type === "tree" ? 0 : 0.8, r.y);
  scene.add(mesh);
  return mesh;
}

function makePlayerMesh(id: string, name: string): THREE.Group {
  const g = new THREE.Group();
  const col = colorFor(id);
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(0.62, 0.8, 0.42),
    stdMat(col),
  );
  body.position.y = 0.9;
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.3, 8, 8),
    stdMat("#" + col.slice(1)),
  );
  head.position.y = 1.55;
  g.add(body);
  g.add(head);

  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.font = "bold 34px sans-serif";
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(10,16,26,0.7)";
  ctx.fillRect(0, 0, 256, 64);
  ctx.fillStyle = "#ffffff";
  ctx.fillText(name, 128, 42);
  const tex = new THREE.CanvasTexture(canvas);
  const spr = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: tex, depthTest: false }),
  );
  spr.scale.set(2.6, 0.65, 1);
  spr.position.y = 2.25;
  g.add(spr);

  scene.add(g);
  return g;
}

// ---- animation loop -----------------------------------------------------
function animate() {
  requestAnimationFrame(animate);
  controls.update();

  // Tween players toward server positions.
  for (const [id, tgt] of state.playerTweens) {
    const obj = state.playerObjs.get(id);
    if (!obj) continue;
    obj.position.x += (tgt.x - obj.position.x) * 0.16;
    obj.position.z += (tgt.y - obj.position.z) * 0.16;
  }
  renderer.render(scene, camera);
}

function startLoop() {
  animate();
  setInterval(pollGame, 100);
}

// ---- world updates from server -----------------------------------------
function applyGame(snap: GameSnap) {
  if (snap.you) {
    state.you = snap.you;
    myId = snap.you.id;
    renderHUD();
  }
  state.online = snap.players ? snap.players.length : 0;
  el("hud-online").textContent = String(state.online);

  // Resources.
  const seen = new Set<string>();
  if (snap.resources) {
    for (const r of snap.resources) {
      seen.add(r.id);
      state.resources.set(r.id, r);
      let obj = state.resourceObjs.get(r.id);
      if (!obj) {
        obj = makeResourceMesh(r);
        state.resourceObjs.set(r.id, obj);
      }
      obj.visible = r.alive;
      // Scale foliage/amount feedback.
      const frac = r.maxAmount > 0 ? r.amount / r.maxAmount : 1;
      obj.scale.setScalar(0.45 + 0.55 * Math.max(0.12, frac));
    }
  }
  for (const [id, obj] of state.resourceObjs) {
    if (!seen.has(id)) {
      scene.remove(obj);
      state.resourceObjs.delete(id);
    }
  }

  // Players.
  const pseen = new Set<string>();
  if (snap.players) {
    for (const p of snap.players) {
      pseen.add(p.id);
      state.players.set(p.id, p);
      let obj = state.playerObjs.get(p.id);
      if (!obj) {
        obj = makePlayerMesh(p.id, p.name || "?");
        state.playerObjs.set(p.id, obj);
      }
      state.playerTweens.set(p.id, { x: p.x, y: p.y });
    }
  }
  for (const [id, obj] of state.playerObjs) {
    if (!pseen.has(id)) {
      scene.remove(obj);
      state.playerObjs.delete(id);
    }
  }
}

// ---- HUD -----------------------------------------------------------------
function renderHUD() {
  const you = state.you;
  if (!you) return;
  el("hud-name").textContent = you.name;
  el("hud-mining").textContent = String(you.miningLevel);
  el("hud-wood").textContent = String(you.woodcuttingLevel);
  el("hud-gold").textContent = String(you.goldCents);
  el("hud-wallet").textContent = money(you.walletCents);
  el("hud-side-gold").textContent =
    "Carrying: " + you.goldCents + " coins · Wallet: " + money(you.walletCents);
  if (you.gathering) el("hud-gold").textContent += " ⇄";

  renderInventory(you.inventory, you.bank);
  renderSkills(you);
}

function renderInventory(
  inv: Record<string, number>,
  bank: Record<string, number>,
) {
  const ul = el("inventory-list");
  const items = Object.keys(inv).sort();
  if (items.length === 0) {
    ul.innerHTML = '<li><span class="dim">empty</span></li>';
    return;
  }
  ul.innerHTML = items
    .map(
      (item) => `
    <li>
      <span>${esc(item)} × ${inv[item]} <span class="dim">(bank ${bank[item] || 0})</span></span>
      <span class="btns">
        <button data-act="bank" data-item="${item}" data-qty="${inv[item]}">Bank</button>
        <button class="sell" data-act="sell" data-item="${item}" data-qty="${inv[item]}">Sell</button>
      </span>
    </li>`,
    )
    .join("");
}

function renderSkills(you: SelfSnap) {
  const skills = [
    { name: "Mining", xp: you.miningXp, lvl: you.miningLevel },
    { name: "Woodcutting", xp: you.woodcuttingXp, lvl: you.woodcuttingLevel },
  ];
  const box = el("skills-list");
  box.innerHTML = skills
    .map((s) => {
      const pct = Math.min(100, (s.xp % 100) * 10);
      return `<div class="skill">
      <div><span>${s.name}</span><b>Lv ${s.lvl} · ${Math.floor(s.xp)} xp</b></div>
      <div class="bar"><div style="width:${pct}%"></div></div>
    </div>`;
    })
    .join("");
}

function log(msg: string) {
  const box = el("log");
  const ln = document.createElement("div");
  ln.className = "ln";
  ln.textContent = msg;
  box.prepend(ln);
  while (box.childNodes.length > 20) box.removeChild(box.lastChild!);
}

// ---- interaction ----------------------------------------------------------
function ndcFromEvent(ev: { clientX: number; clientY: number }) {
  const rect = renderer.domElement.getBoundingClientRect();
  return {
    x: ((ev.clientX - rect.left) / rect.width) * 2 - 1,
    y: -((ev.clientY - rect.top) / rect.height) * 2 + 1,
  };
}

async function onGroundClick(x: number, z: number) {
  const w = state.world;
  if (!w) return;
  x = Math.max(0.5, Math.min(w.w - 0.5, x));
  z = Math.max(0.5, Math.min(w.h - 0.5, z));

  // Prefer gathering a nearby resource under the cursor.
  let best: ResourceSnap | null = null,
    bestD = 2.6;
  for (const r of state.resources.values()) {
    if (!r.alive) continue;
    const d = Math.hypot(r.x - x, r.y - z);
    if (d < bestD) {
      bestD = d;
      best = r;
    }
  }
  if (best) {
    await tryGather(best.id);
    return;
  }

  try {
    await post("/api/move", { token: state.token, x, y: z });
  } catch (e) {
    log("move: " + (e instanceof Error ? e.message : String(e)));
  }
}

async function tryGather(id: string) {
  if (gatherBusy) return;
  gatherBusy = true;
  try {
    await post("/api/gather", { token: state.token, resourceId: id });
  } catch (e) {
    const status = (e as { status?: number }).status;
    const message = e instanceof Error ? e.message : String(e);
    if (status === 202) {
      log("Moving to gather — walk closer.");
    } else if (status === 409) {
      log(message);
    } else {
      log("gather: " + message);
    }
  } finally {
    gatherBusy = false;
  }
}

function bindEvents() {
  if (!renderer || !renderer.domElement) {
    console.error("[mmo] bindEvents skipped: renderer missing");
    return;
  }
  renderer.domElement.addEventListener("pointerdown", (ev) => {
    const overlay = el("overlay");
    if (overlay.style.display !== "none" && !overlay.hidden && !state.you) {
      return;
    }
    clickRaycaster.setFromCamera(ndcFromEvent(ev), camera);
    const pt = new THREE.Vector3();
    if (!clickRaycaster.ray.intersectPlane(groundPlane, pt)) return;
    onGroundClick(pt.x, pt.z);
  });

  el("inventory-panel").addEventListener("click", async (ev) => {
    const btn = (ev.target as HTMLElement | null)?.closest(
      "button[data-act]",
    ) as HTMLElement | null;
    if (!btn) return;
    const act = btn.dataset.act ?? "bank";
    const item = btn.dataset.item ?? "";
    const qty = Number(btn.dataset.qty);
    const path = act === "bank" ? "/api/bank" : "/api/sell";
    try {
      const r = await post<{ coins?: number }>(path, {
        token: state.token,
        item,
        qty,
      });
      log(
        (act === "bank" ? "Banked " : "Sold ") +
          qty +
          " " +
          item +
          (r.coins ? " for " + money(r.coins) + " coins → wallet" : ""),
      );
    } catch (e) {
      log(e instanceof Error ? e.message : String(e));
    }
  });

  el("gold-deposit").addEventListener("click", async () => {
    const cents = state.you ? state.you.goldCents : 0;
    if (!cents) {
      log("You are not carrying any gold.");
      return;
    }
    try {
      await post("/api/deposit_gold", {
        token: state.token,
        amountCents: cents,
      });
      log("Deposited " + money(cents) + " into your shared wallet.");
    } catch (e) {
      log(e instanceof Error ? e.message : String(e));
    }
  });

  el<HTMLFormElement>("join-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name =
      el<HTMLInputElement>("name-input").value.trim() || "Adventurer";
    await join(name, state.token);
  });
}

// ---- join / resume ---------------------------------------------------------
async function join(name: string, token: string | null) {
  const err = el("error-note");
  err.hidden = true;
  try {
    const r = await post<JoinResp>("/api/join", {
      name,
      token: token || undefined,
    });
    state.token = r.token;
    state.name = r.name;
    storage.setItem(WALLET_TOKEN, r.token);
    storage.setItem(WALLET_NAME, r.name);
    enterGame();
  } catch (e) {
    err.textContent =
      "Join failed: " + (e instanceof Error ? e.message : String(e));
    err.hidden = false;
  }
}

function enterGame() {
  el("overlay").style.display = "none";
  el("hud").hidden = false;
  log(
    "Welcome to boom-bot MMO. Click ground to walk, click trees/rocks to gather.",
  );
}

async function pollGame() {
  if (!state.token) return;
  try {
    const snap = await api<GameSnap>(
      "/api/game?token=" + encodeURIComponent(state.token),
    );
    applyGame(snap);
  } catch (e) {
    // transient; ignore
  }
}

async function boot() {
  initScene();
  try {
    const w = await api<WorldSnap>("/api/world");
    buildWorld(w);
  } catch (e) {
    el("error-note").textContent =
      "Could not load world: " + (e instanceof Error ? e.message : String(e));
    el("error-note").hidden = false;
  }
  startLoop();

  if (state.token && storage.getItem(WALLET_NAME)) {
    el("resume-note").hidden = false;
    // Non-blocking resume attempt; fall back to join form.
    join(storage.getItem(WALLET_NAME) || "", state.token);
  }
}

window.addEventListener("error", (ev) => {
  console.error(
    "[mmo] uncaught error:",
    ev.message,
    "@",
    ev.filename + ":" + ev.lineno,
  );
});
window.addEventListener("unhandledrejection", (ev) => {
  console.error("[mmo] unhandled rejection:", ev.reason);
});

document.addEventListener("DOMContentLoaded", () => {
  boot();
  bindEvents();
});
