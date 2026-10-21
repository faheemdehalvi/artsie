import { execFile } from "node:child_process";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { Validator, type Schema } from "@cfworker/json-schema";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const CACHE = path.join(ROOT, "config/cli-tools.json");
export const APPS = [
  "photocraft",
  "vectorcraft",
  "filmcraft",
  "lightcraft",
  "pdfcraft",
  "effectcraft",
  "designcraft",
  "figcraft",
  "wordcraft",
  "soundcraft",
  "deckcraft",
  "cadcraft",
  "gridcraft",
] as const;
export type App = (typeof APPS)[number];
export type Mode = "headless" | "live";
export interface NativeTool {
  name: string;
  description?: string;
  inputSchema: Schema;
}
export interface Catalog {
  updatedAt: string;
  apps: Array<{ id: App; name: string; version: string; tools: NativeTool[] }>;
}

export async function bridge(
  action: string,
  args: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  const runtime = JSON.parse(await fs.readFile(path.join(ROOT, "config/runtime.json"), "utf8")) as {
    python: string;
  };
  return new Promise((resolve, reject) => {
    const child = execFile(
      runtime.python,
      [path.join(ROOT, "cli/bridge.py")],
      {
        cwd: ROOT,
        encoding: "utf8",
        timeout: 165_000,
        maxBuffer: 32 * 1024 * 1024,
      },
      (error, stdout) => {
        try {
          const response = JSON.parse(stdout) as {
            ok: boolean;
            value?: Record<string, unknown>;
            error?: string;
          };
          if (!response.ok) reject(new Error(response.error ?? "ARTsie request failed"));
          else if (error)
            reject(new Error("ARTsie CLI did not complete. Inspect the editor before retrying."));
          else resolve(response.value ?? {});
        } catch {
          reject(
            new Error(
              "ARTsie CLI did not return a result. Its outcome may be unknown; inspect the editor before retrying.",
            ),
          );
        }
      },
    );
    child.stdin?.on("error", () => {});
    child.stdin?.end(JSON.stringify({ action, arguments: args }));
  });
}

export async function discover(app: App, mode: Mode = "headless"): Promise<NativeTool[]> {
  const response = await bridge("tools", { app, mode });
  if (!Array.isArray(response.tools)) throw new Error("ARTsie returned no native tool schemas");
  return response.tools as NativeTool[];
}

export async function readCatalog(): Promise<Catalog | null> {
  try {
    return JSON.parse(await fs.readFile(CACHE, "utf8")) as Catalog;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}

export async function refreshCatalog(): Promise<Catalog> {
  const result = await bridge("apps");
  const installed = result.apps as Array<{ id: App; name: string; version: string; cli: boolean }>;
  const apps: Catalog["apps"] = [];
  for (const app of installed.filter((app) => APPS.includes(app.id) && app.cli)) {
    apps.push({ id: app.id, name: app.name, version: app.version, tools: await discover(app.id) });
  }
  const catalog = { updatedAt: new Date().toISOString(), apps };
  const temp = CACHE + `.${process.pid}.tmp`;
  await fs.writeFile(temp, JSON.stringify(catalog, null, 2) + "\n");
  await fs.rename(temp, CACHE);
  return catalog;
}

export async function parseInput(input: string): Promise<Record<string, unknown>> {
  let text = input;
  if (input.startsWith("@")) text = await fs.readFile(path.resolve(input.slice(1)), "utf8");
  if (input === "-") {
    const chunks: Buffer[] = [];
    for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
    text = Buffer.concat(chunks).toString("utf8");
  }
  const value: unknown = JSON.parse(text);
  if (value === null || Array.isArray(value) || typeof value !== "object")
    throw new Error("Native arguments must be a JSON object");
  return value as Record<string, unknown>;
}

export async function callNative(
  app: App,
  tool: string,
  input: string,
  mode: Mode,
): Promise<Record<string, unknown>> {
  const schema = (await discover(app, mode)).find((candidate) => candidate.name === tool);
  if (!schema) throw new Error(`Unknown ${app} tool: ${tool}. Run artsie tools ${app} first.`);
  const args = await parseInput(input);
  const validation = new Validator(schema.inputSchema).validate(args);
  if (!validation.valid)
    throw new Error(
      `Invalid ${tool} arguments: ${validation.errors.map((error) => error.error).join("; ")}`,
    );
  const result = await bridge("call", { app, tool, arguments: args, mode });
  if (result.isError) {
    const content = Array.isArray(result.content)
      ? (result.content as Array<{ type: string; text?: string }>)
      : [];
    throw new Error(
      content
        .filter((item) => item.type === "text")
        .map((item) => item.text)
        .join("\n") || "The native editor reported an error. Inspect its state before retrying.",
    );
  }
  return result;
}
