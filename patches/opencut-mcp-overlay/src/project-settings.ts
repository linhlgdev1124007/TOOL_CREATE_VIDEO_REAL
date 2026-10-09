import { evalInEditor } from "./browser.js";

export async function setProjectSettings(input: { width: number; height: number; fps: number }) {
	return evalInEditor(`
		await window.__editor.project.updateSettings({ settings: {
			canvasSize: { width: args.width, height: args.height },
			fps: { numerator: args.fps, denominator: 1 },
		} });
		return window.__editor.project.getActive().settings;
	`, input);
}
