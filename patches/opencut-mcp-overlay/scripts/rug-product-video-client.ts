import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const mcpRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mcpRoot, "..");
const mediaRoot = resolve(projectRoot, "product-video/media");
const outputRoot = resolve(projectRoot, "product-video/output");
const browserCache = resolve(projectRoot, ".cache/ms-playwright");

const transport = new StdioClientTransport({
	command: "bun",
	args: ["run", "src/index.ts"],
	cwd: mcpRoot,
	env: {
		...process.env,
		OPENCUT_BASE_URL: "http://localhost:3000",
		OPENCUT_HEADLESS: "true",
		PLAYWRIGHT_BROWSERS_PATH: browserCache,
	},
});

const client = new Client(
	{ name: "rug-product-video-client", version: "1.0.0" },
	{ capabilities: {} },
);

async function call<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
	const response = await client.callTool({ name, arguments: args });
	const content = response.content as Array<{ type: string; text?: string }>;
	const text = content.find((item) => item.type === "text")?.text ?? "null";
	if (response.isError) throw new Error(`${name}: ${text}`);
	return JSON.parse(text) as T;
}

async function main() {
	await client.connect(transport);
	console.log(`MCP connected: ${(await client.listTools()).tools.length} tools`);

	const scenes = [
		{ file: "scene-1.mp4", start: 0, duration: 3.3, name: "Hook" },
		{ file: "scene-2.mp4", start: 3.3, duration: 3.4, name: "3D detail" },
		{ file: "scene-3.mp4", start: 6.7, duration: 3.3, name: "CTA" },
	];

	let videoTrackId: string | undefined;
	for (const scene of scenes) {
		const asset = await call<{ id: string; name: string }>("opencut_add_media", {
			filePath: resolve(mediaRoot, scene.file),
		});
		const inserted = await call<{ trackId?: string }>("opencut_insert_clip", {
			mediaId: asset.id,
			elementType: "video",
			startTime: scene.start,
			duration: scene.duration,
			name: scene.name,
			...(videoTrackId ? { trackId: videoTrackId } : {}),
		});
		videoTrackId ??= inserted.trackId;
		console.log(`Placed ${scene.name} at ${scene.start}s`);
	}

	const music = await call<{ id: string }>("opencut_add_media", {
		filePath: resolve(mediaRoot, "cinematic-bgm.mp3"),
	});
	await call("opencut_insert_clip", {
		mediaId: music.id,
		elementType: "audio",
		startTime: 0,
		duration: 10,
		name: "Cinematic product bed",
	});

	const state = await call<{ duration: number }>("opencut_get_state");
	console.log(`Timeline ready: ${state.duration} ticks`);

	await call("opencut_screenshot", {
		path: resolve(outputRoot, "rug-ad-timeline.png"),
	});
	const exported = await call<{ success: boolean; path?: string; byteLength?: number; error?: string }>(
		"opencut_export",
		{
			format: "mp4",
			quality: "medium",
			includeAudio: true,
			outputPath: resolve(outputRoot, "rug-product-ad-us.mp4"),
		},
	);
	if (!exported.success || !exported.path) {
		throw new Error(`Export failed: ${JSON.stringify(exported)}`);
	}
	console.log(`Exported: ${exported.path} (${exported.byteLength} bytes)`);
}

main()
	.then(async () => {
		await Promise.race([
			client.close(),
			new Promise((resolve) => setTimeout(resolve, 2_000)),
		]);
		process.exit(0);
	})
	.catch(async (error) => {
		console.error(error);
		await Promise.race([
			client.close(),
			new Promise((resolve) => setTimeout(resolve, 2_000)),
		]);
		process.exit(1);
	});
