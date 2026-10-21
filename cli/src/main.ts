import { Cli, z } from "incur";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { pathToFileURL } from "node:url";
import { APPS, ROOT, bridge, callNative, discover, readCatalog, refreshCatalog } from "./client.ts";

const appSchema = z.enum(APPS);
const modeSchema = z.enum(["headless", "live"]).default("headless");
const nativeOptions = z.object({
  input: z
    .string()
    .default("{}")
    .describe("Native arguments as JSON, @/path/to/args.json, or - for stdin"),
  mode: modeSchema,
});
const cli = Cli.create("artsie", {
  version: "1.0.0",
  description:
    "Control all 13 ARTsie creative apps from FD CODE through the shared local editing service.",
});

cli.command("status", {
  description: "Inspect the shared service and installed app connections",
  async run() {
    const value = await bridge("apps");
    const apps = value.apps as Array<{
      id: string;
      installed: boolean;
      cli: boolean;
      session: string;
    }>;
    return {
      service: "ARTsie",
      workspace: path.join(ROOT, "workspace"),
      apps: apps.map(({ id, installed, cli, session }) => ({ id, installed, cli, session })),
    };
  },
});
cli.command("apps", {
  description: "List all apps, versions, file scopes and available native CLIs",
  run: () => bridge("apps"),
});
cli.command("tools", {
  description: "Discover current native tool names and argument schemas for an app",
  args: z.object({ app: appSchema }),
  options: z.object({ mode: modeSchema, query: z.string().optional() }),
  async run({ args, options }) {
    const tools = await discover(args.app, options.mode);
    return {
      app: args.app,
      mode: options.mode,
      tools: tools.filter(
        (tool) =>
          !options.query ||
          `${tool.name} ${tool.description}`.toLowerCase().includes(options.query.toLowerCase()),
      ),
    };
  },
});
cli.command("schema", {
  description: "Read the exact live schema of one native tool",
  args: z.object({ app: appSchema, tool: z.string() }),
  options: z.object({ mode: modeSchema }),
  async run({ args, options }) {
    const tool = (await discover(args.app, options.mode)).find((tool) => tool.name === args.tool);
    if (!tool) throw new Error("Tool not found. Discover the app's tools first.");
    return { app: args.app, mode: options.mode, ...tool };
  },
});
cli.command("call", {
  description:
    "Validate arguments and execute one native tool. Reuses the editor document; never retries a mutation automatically.",
  args: z.object({ app: appSchema, tool: z.string() }),
  options: nativeOptions,
  run: ({ args, options }) => callNative(args.app, args.tool, options.input, options.mode),
});
cli.command("search", {
  description: "Find native operations across every app by name or description",
  args: z.object({ query: z.string() }),
  options: z.object({ limit: z.number().int().min(1).max(100).default(15) }),
  async run({ args, options }) {
    const catalog = (await readCatalog()) ?? (await refreshCatalog());
    const terms = args.query.toLowerCase().split(/\s+/).filter(Boolean);
    const matches = catalog.apps
      .flatMap((app) =>
        app.tools.map((tool) => ({
          app: app.id,
          name: tool.name,
          description: tool.description ?? "",
          score: terms.reduce(
            (score, term) =>
              score +
              (tool.name.toLowerCase().includes(term) ? 4 : 0) +
              (tool.description?.toLowerCase().includes(term) ? 1 : 0),
            0,
          ),
        })),
      )
      .filter((tool) => tool.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, options.limit);
    return { catalogUpdatedAt: catalog.updatedAt, matches };
  },
});
const catalog = Cli.create("catalog", {
  description: "Maintain the native schema discovery index",
});
catalog.command("refresh", {
  description: "Refresh all installed app schemas without changing their documents",
  async run() {
    const value = await refreshCatalog();
    return {
      updatedAt: value.updatedAt,
      apps: value.apps.map((app) => ({
        app: app.id,
        version: app.version,
        tools: app.tools.length,
      })),
      totalTools: value.apps.reduce((sum, app) => sum + app.tools.length, 0),
    };
  },
});
cli.command(catalog);
cli.command("files", {
  description: "List a shared workspace folder",
  args: z.object({ path: z.string().default(".") }),
  run: ({ args }) => bridge("files", args),
});
cli.command("mkdir", {
  description: "Create a workspace folder; refuses overwrite",
  args: z.object({ path: z.string() }),
  run: ({ args }) => bridge("mkdir", args),
});
cli.command("copy", {
  description: "Copy a workspace file or folder; refuses overwrite",
  args: z.object({ source: z.string(), target: z.string() }),
  run: ({ args }) => bridge("copy", args),
});
cli.command("move", {
  description: "Move or rename a workspace file; refuses overwrite",
  args: z.object({ source: z.string(), target: z.string() }),
  run: ({ args }) => bridge("rename", args),
});
cli.command("import", {
  description: "Copy a local file into Inbox for confined native editors; preserves the original",
  args: z.object({ source: z.string() }),
  options: z.object({ name: z.string().optional() }),
  async run({ args, options }) {
    const source = await fs.realpath(path.resolve(args.source));
    if (!(await fs.stat(source)).isFile())
      throw new Error("Import accepts one regular file; use the hub for folders.");
    const name = options.name ?? path.basename(source);
    if (name !== path.basename(name) || name === "." || name === "..")
      throw new Error("Choose a filename without folder components");
    const inbox = await fs.realpath(path.join(ROOT, "workspace/Inbox"));
    if (!inbox.startsWith(path.join(ROOT, "workspace") + path.sep))
      throw new Error("Inbox escapes the ARTsie workspace");
    const target = path.join(inbox, name);
    await fs.copyFile(source, target, 1);
    return { source, path: `Inbox/${name}`, absolutePath: target, originalPreserved: true };
  },
});
cli.command("launch", {
  description: "Open a native editor, optionally with a workspace-relative file",
  args: z.object({ app: appSchema, path: z.string().optional() }),
  run: ({ args }) => bridge("launch", args),
});
cli.command("live", {
  description: "Open a visible PhotoCraft or FilmCraft agent window; then use --mode live",
  args: z.object({ app: z.enum(["photocraft", "filmcraft"]) }),
  run: ({ args }) => bridge("start_live", args),
});

const cached = await readCatalog();
for (const app of APPS) {
  const group = Cli.create(app, {
    description: `${app}: native editor tools, sharing the hub's persistent document`,
  });
  group.command("tools", {
    description: "Discover this app's exact schemas",
    options: z.object({ mode: modeSchema }),
    async run({ options }) {
      return { app, tools: await discover(app, options.mode) };
    },
  });
  group.command("call", {
    description: "Run any discovered native tool",
    args: z.object({ tool: z.string() }),
    options: nativeOptions,
    run: ({ args, options }) => callNative(app, args.tool, options.input, options.mode),
  });
  for (const tool of cached?.apps.find((item) => item.id === app)?.tools ?? []) {
    if (["tools", "call"].includes(tool.name)) continue;
    group.command(tool.name, {
      description: (tool.description ?? tool.name).slice(0, 500),
      options: nativeOptions,
      run: ({ options }) => callNative(app, tool.name, options.input, options.mode),
    });
  }
  cli.command(group);
}

export default cli;
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await cli.serve();
