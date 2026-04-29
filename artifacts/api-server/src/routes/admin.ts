import { Router, type IRouter, type Request, type Response, type NextFunction } from "express";
import fs from "node:fs/promises";
import path from "node:path";

const router: IRouter = Router();

const CONFIG_FILE = "/home/runner/workspace/bot/data/config.json";
const STATS_FILE = "/home/runner/workspace/bot/data/stats.json";

const DEFAULT_GUILD = {
  welcome_channel: null as string | null,
  welcome_image: null as string | null,
  welcome_text: "Selamat datang di **{server}**, {user}! Kamu member ke-**{count}**.",
  welcome_color: "#5865F2",
  goodbye_channel: null as string | null,
  goodbye_image: null as string | null,
  goodbye_text: "Sampai jumpa, **{user}**. 😢",
  goodbye_color: "#ED4245",
  level_up_channel: null as string | null,
  level_up_enabled: true,
  sholat_channel: null as string | null,
  sholat_enabled: false,
  voicemaster_create_channel: null as string | null,
  voicemaster_category: null as string | null,
  confess_channel: null as string | null,
  verify_channel: null as string | null,
  verify_message_id: null as string | null,
  verify_emoji: "✅",
  verify_role: null as string | null,
};

type GuildCfg = typeof DEFAULT_GUILD;

async function loadConfig(): Promise<{ guilds: Record<string, Partial<GuildCfg>> }> {
  try {
    const txt = await fs.readFile(CONFIG_FILE, "utf-8");
    const parsed = JSON.parse(txt);
    if (!parsed.guilds) parsed.guilds = {};
    return parsed;
  } catch {
    return { guilds: {} };
  }
}

async function saveConfig(data: object): Promise<void> {
  await fs.mkdir(path.dirname(CONFIG_FILE), { recursive: true });
  const tmp = CONFIG_FILE + ".tmp";
  await fs.writeFile(tmp, JSON.stringify(data, null, 2), "utf-8");
  await fs.rename(tmp, CONFIG_FILE);
}

function withDefaults(g: Partial<GuildCfg>): GuildCfg {
  return { ...DEFAULT_GUILD, ...g };
}

function basicAuth(req: Request, res: Response, next: NextFunction) {
  const secret = process.env["SESSION_SECRET"];
  if (!secret) {
    res.status(500).send("Server missing SESSION_SECRET");
    return;
  }
  const header = req.headers.authorization;
  if (!header || !header.startsWith("Basic ")) {
    res.set("WWW-Authenticate", 'Basic realm="Lunethra Admin"').status(401).send("Auth required");
    return;
  }
  try {
    const decoded = Buffer.from(header.slice(6), "base64").toString("utf-8");
    const [user, pass] = decoded.split(":", 2);
    if (user === "admin" && pass === secret) {
      next();
      return;
    }
  } catch {
    // fall through
  }
  res.set("WWW-Authenticate", 'Basic realm="Lunethra Admin"').status(401).send("Invalid credentials");
}

router.get("/admin", basicAuth, (_req, res) => {
  res.set("Content-Type", "text/html; charset=utf-8").send(ADMIN_HTML);
});

router.get("/admin/config/:guildId", basicAuth, async (req, res) => {
  const guildId = req.params["guildId"];
  if (!guildId || !/^\d+$/.test(guildId)) {
    res.status(400).json({ error: "invalid guild id" });
    return;
  }
  const data = await loadConfig();
  const g = withDefaults(data.guilds[guildId] || {});
  res.json({ guildId, config: g });
});

router.put("/admin/config/:guildId", basicAuth, async (req, res) => {
  const guildId = req.params["guildId"];
  if (!guildId || !/^\d+$/.test(guildId)) {
    res.status(400).json({ error: "invalid guild id" });
    return;
  }
  const body = req.body as Partial<GuildCfg>;
  const data = await loadConfig();
  const current = withDefaults(data.guilds[guildId] || {});
  const updated: GuildCfg = { ...current };
  for (const key of Object.keys(DEFAULT_GUILD) as (keyof GuildCfg)[]) {
    if (key in body) {
      const v = body[key];
      // Empty string -> null for nullable channel/image fields
      if (v === "" && (key.endsWith("_channel") || key.endsWith("_image") || key.endsWith("_category"))) {
        (updated as Record<string, unknown>)[key] = null;
      } else {
        (updated as Record<string, unknown>)[key] = v as unknown;
      }
    }
  }
  data.guilds[guildId] = updated;
  await saveConfig(data);
  res.json({ guildId, config: updated, saved: true });
});

router.get("/admin/stats", basicAuth, async (_req, res) => {
  try {
    const txt = await fs.readFile(STATS_FILE, "utf-8");
    const data = JSON.parse(txt);
    const summary: Record<string, { users: number; total_xp: number; total_points: number }> = {};
    for (const [guildId, users] of Object.entries(data as Record<string, Record<string, { xp?: number; points?: number }>>)) {
      let xp = 0;
      let pts = 0;
      const userCount = Object.keys(users).length;
      for (const u of Object.values(users)) {
        xp += u.xp || 0;
        pts += u.points || 0;
      }
      summary[guildId] = { users: userCount, total_xp: xp, total_points: pts };
    }
    res.json({ summary });
  } catch {
    res.json({ summary: {} });
  }
});

const ADMIN_HTML = `<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lunethra Admin Panel</title>
<style>
  :root {
    --bg: #0e1014; --panel: #181b22; --border: #2a2e38;
    --text: #e9eaee; --muted: #8a8f99; --accent: #b18cff; --accent-2: #ff6fbf;
    --good: #57f287; --bad: #ed4245;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background: linear-gradient(180deg, #0a0c10, #14171f); color: var(--text); min-height: 100vh; }
  header { padding: 32px 24px; border-bottom: 1px solid var(--border); background: linear-gradient(90deg, #1a1530, #0f1424); }
  header h1 { margin: 0; font-size: 28px; letter-spacing: 0.5px;
              background: linear-gradient(90deg, var(--accent), var(--accent-2));
              -webkit-background-clip: text; background-clip: text; color: transparent; }
  header p { margin: 6px 0 0; color: var(--muted); font-size: 14px; }
  main { max-width: 980px; margin: 0 auto; padding: 28px 20px 80px; display: grid; gap: 20px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 22px; }
  .card h2 { margin: 0 0 14px; font-size: 18px; }
  .row { display: grid; grid-template-columns: 220px 1fr; gap: 12px; align-items: center; padding: 8px 0; }
  .row label { color: var(--muted); font-size: 13px; }
  input, textarea, select { width: 100%; background: #0f1218; color: var(--text);
                             border: 1px solid var(--border); border-radius: 9px; padding: 10px 12px; font: inherit; }
  input:focus, textarea:focus { outline: none; border-color: var(--accent); }
  textarea { min-height: 80px; resize: vertical; }
  input[type=checkbox] { width: auto; }
  input[type=color] { padding: 4px; height: 40px; width: 80px; }
  button { background: linear-gradient(90deg, var(--accent), var(--accent-2)); color: #0d0f15; border: 0;
           padding: 12px 22px; border-radius: 10px; font-weight: 700; cursor: pointer; font-size: 14px; }
  button.secondary { background: #2a2e38; color: var(--text); }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; }
  .pill { display: inline-block; padding: 3px 10px; border-radius: 99px; background: #25212e;
          color: var(--accent); font-size: 11px; letter-spacing: 0.5px; }
  .status { padding: 10px 14px; border-radius: 9px; margin-top: 12px; font-size: 13px; display: none; }
  .status.ok { background: #143820; color: var(--good); display: block; }
  .status.err { background: #3b1416; color: var(--bad); display: block; }
  .commands { columns: 2; column-gap: 24px; }
  .commands p { break-inside: avoid; margin: 4px 0; font-size: 13px; }
  code { background: #0f1218; padding: 2px 6px; border-radius: 4px; color: var(--accent); font-size: 12px; }
  small { color: var(--muted); font-size: 11px; display: block; margin-top: 4px; }
  .hint { color: var(--muted); font-size: 12px; margin: 6px 0 14px; }
</style>
</head>
<body>
<header>
  <h1>✶ LUNETHRA ✶ — Admin Panel</h1>
  <p>Atur welcome, goodbye, sholat, voicemaster, confess & lainnya per server.</p>
</header>
<main>

  <section class="card">
    <h2>1. Pilih Server</h2>
    <p class="hint">Tempel <strong>Guild ID</strong> Discord kamu di sini. Cara dapatin: Aktifkan Developer Mode di Discord → klik kanan icon server → "Copy Server ID".</p>
    <div class="toolbar">
      <input id="guildId" placeholder="Contoh: 1234567890123456789" inputmode="numeric" />
      <button id="loadBtn">Muat Konfigurasi</button>
    </div>
    <div id="status" class="status"></div>
  </section>

  <section class="card" id="configCard" style="display:none">
    <h2>2. Welcome <span class="pill">on_member_join</span></h2>
    <div class="row"><label>Welcome Channel ID</label><input id="welcome_channel" placeholder="ID channel teks" /></div>
    <div class="row"><label>Welcome Background URL</label><input id="welcome_image" placeholder="https://... (gambar PNG/JPG)" /></div>
    <div class="row"><label>Welcome Text</label><textarea id="welcome_text"></textarea></div>
    <small>Variabel: <code>{user}</code> <code>{username}</code> <code>{server}</code> <code>{count}</code></small>
    <div class="row"><label>Warna Embed</label><input type="color" id="welcome_color" /></div>
  </section>

  <section class="card" id="goodbyeCard" style="display:none">
    <h2>3. Goodbye <span class="pill">on_member_remove</span></h2>
    <div class="row"><label>Goodbye Channel ID</label><input id="goodbye_channel" /></div>
    <div class="row"><label>Goodbye Background URL</label><input id="goodbye_image" /></div>
    <div class="row"><label>Goodbye Text</label><textarea id="goodbye_text"></textarea></div>
    <div class="row"><label>Warna Embed</label><input type="color" id="goodbye_color" /></div>
  </section>

  <section class="card" id="levelCard" style="display:none">
    <h2>4. Level Up Notification</h2>
    <div class="row"><label>Aktifkan</label><input type="checkbox" id="level_up_enabled" /></div>
    <div class="row"><label>Channel (opsional)</label><input id="level_up_channel" placeholder="Kosong = di channel chat" /></div>
  </section>

  <section class="card" id="sholatCard" style="display:none">
    <h2>5. Pengingat Sholat (WIB)</h2>
    <div class="row"><label>Aktifkan</label><input type="checkbox" id="sholat_enabled" /></div>
    <div class="row"><label>Channel ID</label><input id="sholat_channel" placeholder="Kosong = auto-detect #truth-or-dare" /></div>
  </section>

  <section class="card" id="vmCard" style="display:none">
    <h2>6. Voicemaster</h2>
    <div class="row"><label>Create Voice Channel ID</label><input id="voicemaster_create_channel" placeholder='ID channel "✗》Create voice"' /></div>
    <div class="row"><label>Kategori (opsional)</label><input id="voicemaster_category" placeholder="ID category Discord" /></div>
    <small>Atau pakai <code>/createvoice</code> di Discord buat auto-bikin channel pemicu.</small>
  </section>

  <section class="card" id="confessCard" style="display:none">
    <h2>7. Confess (Anonim)</h2>
    <div class="row"><label>Confess Channel ID</label><input id="confess_channel" /></div>
  </section>

  <section class="card" id="verifyCard" style="display:none">
    <h2>8. React-to-Verify</h2>
    <div class="row"><label>Verify Channel ID</label><input id="verify_channel" /></div>
    <div class="row"><label>Message ID</label><input id="verify_message_id" placeholder="Auto-isi setelah pakai /setverify" /></div>
    <div class="row"><label>Emoji</label><input id="verify_emoji" placeholder="✅" /></div>
    <div class="row"><label>Role ID</label><input id="verify_role" /></div>
    <small>Lebih gampang pakai <code>/setverify</code> di Discord — message-nya auto-dibikin & ID-nya otomatis ke-set.</small>
  </section>

  <section class="card" id="saveCard" style="display:none">
    <button id="saveBtn">💾 Simpan Semua</button>
    <button class="secondary" id="reloadBtn">↻ Muat Ulang</button>
  </section>

  <section class="card">
    <h2>📖 Daftar Command (Slash)</h2>
    <div class="commands">
      <p><code>/help</code> — bantuan</p>
      <p><code>/level</code> <code>/rank</code> — level system</p>
      <p><code>/dailyclaim</code> — bonus poin harian</p>
      <p><code>/love</code> — tingkat cinta</p>
      <p><code>/calc</code> — kalkulator</p>
      <p><code>/robux</code> — kalkulator Robux</p>
      <p><code>/chat</code> — ngobrol AI</p>
      <p><code>/imagine</code> — generate gambar</p>
      <p><code>/vt</code> <code>/yt</code> <code>/dl</code> — download video</p>
      <p><code>/confess</code> — pesan anonim</p>
      <p><code>/jadwalsholat</code> — jadwal sholat</p>
      <p><code>/setwelcome</code> <code>/setgoodbye</code></p>
      <p><code>/setsholat</code> <code>/setconfess</code></p>
      <p><code>/setvoicemaster</code> <code>/createvoice</code></p>
      <p><code>/testwelcome</code> — preview welcome</p>
      <p><code>/stats</code> <code>/leaderboard</code></p>
      <p><code>/tod</code> — truth or dare</p>
      <p><code>/trivia</code> <code>/8ball</code> <code>/rps</code> ...</p>
      <p><code>/tebakbendera</code> <code>/tebakkpop</code> ...</p>
      <p>Music prefix: <code>m/play</code> <code>m/skip</code> ...</p>
    </div>
  </section>
</main>

<script>
const $ = (id) => document.getElementById(id);
const fields = ["welcome_channel","welcome_image","welcome_text","welcome_color",
  "goodbye_channel","goodbye_image","goodbye_text","goodbye_color",
  "level_up_enabled","level_up_channel","sholat_enabled","sholat_channel",
  "voicemaster_create_channel","voicemaster_category","confess_channel",
  "verify_channel","verify_message_id","verify_emoji","verify_role"];
const cards = ["configCard","goodbyeCard","levelCard","sholatCard","vmCard","confessCard","verifyCard","saveCard"];

function showStatus(msg, ok=true) {
  const s = $("status"); s.textContent = msg; s.className = "status " + (ok?"ok":"err");
}

async function loadConfig() {
  const id = $("guildId").value.trim();
  if (!/^\\d+$/.test(id)) { showStatus("Guild ID harus angka.", false); return; }
  try {
    const r = await fetch("/api/admin/config/" + id);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const c = data.config || {};
    for (const f of fields) {
      const el = $(f);
      if (!el) continue;
      if (el.type === "checkbox") el.checked = !!c[f];
      else el.value = c[f] == null ? "" : c[f];
    }
    cards.forEach(id => $(id).style.display = "block");
    showStatus("Konfigurasi dimuat untuk guild " + id);
  } catch (e) { showStatus("Gagal muat: " + e.message, false); }
}

async function saveConfig() {
  const id = $("guildId").value.trim();
  if (!/^\\d+$/.test(id)) { showStatus("Guild ID harus angka.", false); return; }
  const payload = {};
  for (const f of fields) {
    const el = $(f);
    if (!el) continue;
    if (el.type === "checkbox") payload[f] = el.checked;
    else payload[f] = el.value;
  }
  try {
    const r = await fetch("/api/admin/config/" + id, {
      method: "PUT", headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    showStatus("✅ Tersimpan! Bot akan langsung pakai konfigurasi baru.");
  } catch (e) { showStatus("Gagal simpan: " + e.message, false); }
}

$("loadBtn").addEventListener("click", loadConfig);
$("saveBtn") && $("saveBtn").addEventListener("click", saveConfig);
$("reloadBtn") && $("reloadBtn").addEventListener("click", loadConfig);
$("guildId").addEventListener("keydown", e => { if (e.key === "Enter") loadConfig(); });
</script>
</body>
</html>`;

export default router;
