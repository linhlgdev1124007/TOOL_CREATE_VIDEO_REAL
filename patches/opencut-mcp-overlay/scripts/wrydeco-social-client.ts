import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const mcpRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mcpRoot, "..");
const workRoot = resolve(projectRoot, "work/wrydeco-demo");
const sourceRoot = resolve(projectRoot, "source/Wrydeco_real");
const outputRoot = resolve(projectRoot, "output");

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

const client = new Client({ name: "wrydeco-social-client", version: "1.0.0" }, { capabilities: {} });

async function call<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
	const response = await client.callTool(
		{ name, arguments: args },
		undefined,
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

	const content = await call<{ id: string }>("opencut_add_media", {
		filePath: resolve(workRoot, "wrydeco-content.mp4"),
	});
	const contentClip = await call<{ trackId: string }>("opencut_insert_clip", {
		mediaId: content.id,
		elementType: "video",
		startTime: 0,
		duration: 16.4,
		name: "Wrydeco handcrafted story",
	});

	const outro = await call<{ id: string }>("opencut_add_media", {
		filePath: resolve(sourceRoot, "video_outro/outro_wrydeo.mp4"),
	});
	await call("opencut_insert_clip", {
		mediaId: outro.id,
		elementType: "video",
		trackId: contentClip.trackId,
		startTime: 16.4,
		duration: 2.68,
		name: "Required Wrydeco brand outro",
	});

	const audio = await call<{ id: string }>("opencut_add_media", {
		filePath: resolve(workRoot, "wrydeco-master-audio.m4a"),
	});
	await call("opencut_insert_clip", {
		mediaId: audio.id,
		elementType: "audio",
		startTime: 0,
		duration: 19.08,
		name: "US narration, workshop sound and brand outro",
	});

	await call("opencut_screenshot", { path: resolve(outputRoot, "wrydeco-demo-timeline.png") });
	const exported = await call<{ success: boolean; path?: string; byteLength?: number; error?: string }>(
		"opencut_export",
		{
			format: "mp4",
			quality: "medium",
			includeAudio: true,
			outputPath: resolve(outputRoot, "wrydeco-handcrafted-tree-social-demo.mp4"),
		},
	);
	if (!exported.success || !exported.path) throw new Error(JSON.stringify(exported));
	console.log(`EXPORTED=${exported.path}`);
	console.log(`BYTES=${exported.byteLength}`);
}

main().then(async () => {
	await Promise.race([client.close(), new Promise((resolve) => setTimeout(resolve, 2_000))]);
	process.exit(0);
}).catch(async (error) => {
	console.error(error);
	await Promise.race([client.close(), new Promise((resolve) => setTimeout(resolve, 2_000))]);
	process.exit(1);
});
