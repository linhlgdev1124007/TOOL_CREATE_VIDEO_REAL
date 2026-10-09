import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const mcpRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mcpRoot, "..");
const transport = new StdioClientTransport({
	command: "bun",
	args: ["run", "src/index.ts"],
	cwd: mcpRoot,
	env: {
		...process.env,
		OPENCUT_BASE_URL: "http://localhost:3000",
		OPENCUT_HEADLESS: "true",
		PLAYWRIGHT_BROWSERS_PATH: resolve(projectRoot, ".cache/ms-playwright"),
	},
});
const client = new Client({ name: "wrydeco-bench-client", version: "1.0.0" }, { capabilities: {} });

async function call<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
	const response = await client.callTool(
		{ name, arguments: args }, undefined,
		{ timeout: name === "opencut_export" ? 300_000 : 60_000 },
	);
	const content = response.content as Array<{ type: string; text?: string }>;
	const message = content.find((item) => item.type === "text")?.text ?? "null";
	if (response.isError) throw new Error(`${name}: ${message}`);
	return JSON.parse(message) as T;
}

async function main() {
	await client.connect(transport);
	console.log(`MCP connected: ${(await client.listTools()).tools.length} tools`);
	const work = resolve(projectRoot, "work/hy-video");
	const delivery = resolve(projectRoot, "hy");
	const source = resolve(projectRoot, "source/Wrydeco_real");

	const content = await call<{ id: string }>("opencut_add_media", { filePath: resolve(work, "bench-content.mp4") });
	const first = await call<{ trackId: string }>("opencut_insert_clip", {
		mediaId: content.id, elementType: "video", startTime: 0, duration: 16.4,
		name: "Live-edge bench craftsmanship",
	});
	const outro = await call<{ id: string }>("opencut_add_media", { filePath: resolve(source, "video_outro/outro_wrydeo.mp4") });
	await call("opencut_insert_clip", {
		mediaId: outro.id, elementType: "video", trackId: first.trackId,
		startTime: 16.4, duration: 2.68, name: "Required Wrydeco brand outro",
	});
	const audio = await call<{ id: string }>("opencut_add_media", { filePath: resolve(work, "bench-master-audio.m4a") });
	await call("opencut_insert_clip", {
		mediaId: audio.id, elementType: "audio", startTime: 0, duration: 19.08,
		name: "US voiceover, real workshop sound and brand outro",
	});
	await call("opencut_screenshot", { path: resolve(delivery, "wrydeco-live-edge-bench-timeline.png") });
	const result = await call<{ success: boolean; path?: string; byteLength?: number; error?: string }>("opencut_export", {
		format: "mp4", quality: "medium", includeAudio: true,
		outputPath: resolve(delivery, "wrydeco-live-edge-bench-social-v01.mp4"),
	});
	if (!result.success || !result.path) throw new Error(JSON.stringify(result));
	console.log(`EXPORTED=${result.path}`);
	console.log(`BYTES=${result.byteLength}`);
}

main().then(async () => {
	await Promise.race([client.close(), new Promise((resolve) => setTimeout(resolve, 2_000))]);
	process.exit(0);
}).catch(async (error) => {
	console.error(error);
	await Promise.race([client.close(), new Promise((resolve) => setTimeout(resolve, 2_000))]);
	process.exit(1);
});
