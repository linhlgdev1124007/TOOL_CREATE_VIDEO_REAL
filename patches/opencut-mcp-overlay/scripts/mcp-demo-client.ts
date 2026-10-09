import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const videoPath = resolve(repoRoot, "media/demo-video.mp4");
const audioPath = resolve(repoRoot, "media/demo-bgm.mp3");
const outputPath = resolve(repoRoot, "output/opencut-mcp-demo.mp4");
const screenshotPath = resolve(repoRoot, "output/opencut-mcp-demo.png");

const transport = new StdioClientTransport({
	command: "bun",
	args: ["run", "src/index.ts"],
	cwd: repoRoot,
	env: {
		...process.env,
		OPENCUT_BASE_URL: "http://localhost:3000",
		OPENCUT_HEADLESS: "true",
	},
});

const client = new Client(
	{ name: "opencut-demo-client", version: "1.0.0" },
	{ capabilities: {} },
);

async function call<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
	const response = await client.callTool({ name, arguments: args });
	if (response.isError) throw new Error(`MCP ${name} failed: ${JSON.stringify(response.content)}`);
	const content = response.content as Array<{ type: string; text?: string }>;
	const text = content.find((item) => item.type === "text");
	if (!text || text.type !== "text") throw new Error(`MCP ${name} returned no text result`);
	return JSON.parse(text.text ?? "null") as T;
}

async function main() {
	await client.connect(transport);
	const advertised = await client.listTools();
	console.log(`Connected to MCP server (${advertised.tools.length} tools)`);

	const video = await call<{ id: string; name: string; duration: number }>(
		"opencut_add_media",
		{ filePath: videoPath },
	);
	console.log(`Uploaded video: ${video.name} (${video.duration}s)`);

	const videoClip = await call<{ elementId: string }>("opencut_insert_clip", {
		mediaId: video.id,
		elementType: "video",
		startTime: 0,
		duration: video.duration,
		name: "OpenCut MCP demo",
	});

	const audio = await call<{ id: string; name: string; duration: number }>(
		"opencut_add_media",
		{ filePath: audioPath },
	);
	console.log(`Uploaded audio: ${audio.name} (${audio.duration}s)`);

	await call("opencut_insert_clip", {
		mediaId: audio.id,
		elementType: "audio",
		startTime: 0,
		duration: audio.duration,
		name: "Demo background tone",
	});

	await call("opencut_split_at", {
		elementIds: [videoClip.elementId],
		time: 5,
	});
	console.log("Split video at 5 seconds");

	const state = await call<{ duration: number; tracks: Record<string, unknown[]> }>(
		"opencut_get_state",
	);
	console.log(`Timeline duration: ${state.duration} ticks`);

	await call("opencut_screenshot", { path: screenshotPath });
	const exported = await call<{ success: boolean; path: string; byteLength: number }>(
		"opencut_export",
		{
			format: "mp4",
			quality: "low",
			includeAudio: true,
			outputPath,
		},
	);
	if (!exported.success || !exported.path) {
		throw new Error(`OpenCut export did not produce a file: ${JSON.stringify(exported)}`);
	}
	console.log(`Exported ${exported.path} (${exported.byteLength} bytes)`);
}

main()
	.then(async () => {
		// The PoC server keeps Playwright handles alive after stdio closes on
		// Windows, so do not let cleanup stall an otherwise completed demo.
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
