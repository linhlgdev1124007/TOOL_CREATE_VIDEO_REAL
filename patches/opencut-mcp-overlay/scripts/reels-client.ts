import { spawn, type ChildProcess } from "node:child_process";
import { readFileSync, writeFileSync, appendFileSync, openSync, closeSync } from "node:fs";
import { resolve } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const job = resolve(process.argv[2] ?? "");
if (!process.argv[2]) throw new Error("Usage: bun run scripts/reels-client.ts <job-directory>");
const root = resolve(import.meta.dir, "../..");
const ready = JSON.parse(readFileSync(resolve(job, "prepared.json"), "utf8"));
const render = ready.render ?? { width: 720, height: 1280, fps: 30 };
const port = 3037;
const base = `http://localhost:${port}`;
const env = { ...process.env, TEMP: resolve(root, ".tmp"), TMP: resolve(root, ".tmp"),
	PLAYWRIGHT_BROWSERS_PATH: resolve(root, ".cache/ms-playwright"),
	BUN_INSTALL_CACHE_DIR: resolve(root, ".cache/bun"), OPENCUT_BASE_URL: base, OPENCUT_HEADLESS: "true" };
let web: ChildProcess | undefined;
let client: Client | undefined;
let transport: StdioClientTransport | undefined;

async function killOwned(process: ChildProcess | undefined) {
	if (!process?.pid || process.exitCode !== null) return;
	if (globalThis.process.platform === "win32") {
		await new Promise<void>(done => spawn("taskkill", ["/PID", String(process.pid), "/T", "/F"],
			{ windowsHide: true, stdio: "ignore" }).on("close", () => done()));
	} else process.kill("SIGTERM");
}

async function call(name: string, args: Record<string, unknown> = {}) {
	const response = await client!.callTool({ name, arguments: args }, undefined,
		{ timeout: name === "opencut_export" ? 900_000 : 90_000 });
	const text = (response.content as Array<{type: string; text?: string}>).find(x => x.type === "text")?.text;
	if (response.isError || !text) throw new Error(`${name}: ${text}`);
	return JSON.parse(text);
}

async function connect() {
	transport = new StdioClientTransport({ command: process.execPath, args: ["run", "src/index.ts"],
		cwd: resolve(root, "opencut-mcp"), env: env as Record<string,string>, stderr: "pipe" });
	transport.stderr?.on("data", chunk => appendFileSync(resolve(job, "opencut-mcp.log"), chunk));
	client = new Client({ name: "wrydeco-reels", version: "1.0.0" }, { capabilities: {} });
	await client.connect(transport);
}

async function assemble() {
	const content = await call("opencut_add_media", { filePath: ready.content });
	const outro = await call("opencut_add_media", { filePath: ready.outro });
	const audio = await call("opencut_add_media", { filePath: ready.audio });
	await call("opencut_set_project_settings", render);
	const first = await call("opencut_insert_clip", { mediaId: content.id, elementType: "video",
		startTime: 0, duration: ready.content_duration, name: "Wrydeco story" });
	if (!first.inserted || !first.trackId) throw new Error("Content insert failed");
	const last = await call("opencut_insert_clip", { mediaId: outro.id, elementType: "video",
		trackId: first.trackId, startTime: ready.content_duration, duration: ready.outro_duration, name: "Wrydeco outro" });
	const sound = await call("opencut_insert_clip", { mediaId: audio.id, elementType: "audio",
		startTime: 0, duration: ready.total_duration, name: "Voice + chill music + SFX (no source audio)" });
	if (!last.inserted || !sound.inserted) throw new Error("Timeline insertion failed");
	const state = await call("opencut_get_state");
	writeFileSync(resolve(job, "timeline-state.json"), JSON.stringify(state, null, 2));
	if (Math.abs(state.duration/120000-ready.total_duration) > .04) throw new Error("Timeline duration mismatch");
	await call("opencut_screenshot", { path: resolve(job, "timeline.png") });
	const result = await call("opencut_export", { format: "mp4", quality: "high", fps: render.fps,
		includeAudio: true, outputPath: resolve(job, "opencut-export.mp4") });
	if (!result.success) throw new Error(`Export failed: ${JSON.stringify(result)}`);
	console.log(JSON.stringify(result));
}

try {
	// Dedicated port: do not reuse or terminate a user's unrelated editor session.
	try {
		await fetch(base, { signal: AbortSignal.timeout(1000) });
		throw new Error(`Port ${port} is already occupied. Close its owner or configure a free port.`);
	} catch (err) {
		if (err instanceof Error && err.message.includes("already occupied")) throw err;
	}
	const log = openSync(resolve(job, "opencut-web.log"), "a");
	web = spawn(process.execPath, ["x", "next", "dev", "--turbopack", "--port", String(port)], {
		cwd: resolve(root, "opencut-classic/apps/web"), env, windowsHide: true, stdio: ["ignore", log, log] });
	closeSync(log);
	let available = false;
	for (let i = 0; i < 120; i++) {
		if (web.exitCode !== null) throw new Error("OpenCut exited; inspect opencut-web.log");
		try { const r = await fetch(`${base}/projects`, { signal: AbortSignal.timeout(3000) }); if (r.ok) { available = true; break; } } catch {}
		await new Promise(r => setTimeout(r, 1000));
	}
	if (!available) throw new Error("OpenCut startup timed out");
	for (let attempt = 0; attempt < 2; attempt++) {
		try { await connect(); await assemble(); break; }
		catch (err) { if (attempt === 1) throw err; console.error("Retrying with a fresh MCP session:", err); }
		finally { await client?.close(); client = undefined; }
	}
} finally {
	await client?.close();
	await killOwned(web);
}
