# ARTsie

A local Mac workspace for all 13 apps on [ArtCraft’s app page](https://getartcraft.com/apps), with the official native applications, their CLI tools, matching release source snapshots, and a shared MCP gateway for LLM clients.

**Open `ARTsie.app` or double-click `Start ARTsie.command`.** The hub launches the editors, manages a shared workspace, and exposes the installed apps’ actual tool schemas. It runs at `http://127.0.0.1:8743` on this Mac.

## Install on a new Mac

This repository holds ARTsie's own code. The upstream apps are downloaded during setup, so a clone is about 2 MB rather than 6.5 GB.

### Prerequisites

| Need | Version | Install |
| --- | --- | --- |
| macOS | Apple silicon or Intel (the apps are macOS universal builds) | |
| Python | 3.12 or newer (tested on 3.14.8) | `brew install python@3.14` |
| Node.js | 24.10 or newer (tested on 26.4.0) | `brew install node` |
| Disk | About 7 GB free | |
| Network | github.com, for the ArtCraft releases | |

### Setup

```sh
git clone https://github.com/faheemdehalvi/artsie.git ARTsie
cd ARTsie
./setup.sh
```

`setup.sh` runs these four steps. You can also run them by hand:

```sh
# Python: nothing to install. requirements.txt lists no packages because ARTsie uses only the standard library.
cd cli && npm ci --ignore-scripts --no-audit --no-fund && cd ..   # CLI dependencies (incur, @cfworker/json-schema)
python3 scripts/install_suite.py                # the 13 apps, their CLIs and source snapshots
python3 scripts/install_cli.py                  # puts `artsie` in ~/.local/bin
```

If `npm ci` complains about the lockfile, use `npm install` in `cli/`. For development, `npm install` also adds the TypeScript tooling, `npm run typecheck` checks types and `npm test` runs the CLI tests.

### What setup recreates

These folders are not in the repository. Setup rebuilds them:

| Folder | Size | Made by |
| --- | --- | --- |
| `downloads/` | about 2 GB | `install_suite.py` fetches each app's macOS installer and CLI archive. It uses the committed `release.json` and checks every file against the committed `SHA256SUMS.txt`, so you get the same pinned versions. |
| `Applications/` | about 2.2 GB | `install_suite.py` copies each app out of its installer and verifies the vendor code signature. |
| `tools/` and `bin/*-cli` | about 1.6 GB | `install_suite.py` unpacks each app's CLI and links it into `bin/`. |
| `sources/` | about 355 MB | `install_suite.py` downloads the source archive for the same release tag from github.com/storytold. |
| `cli/node_modules/` | | `npm ci` |
| `workspace/Inbox`, `Projects`, `Exports` | empty | `install_suite.py` creates them. Your own files live here and never go into git. |
| `logs/` and `data/photocraft-control-token` | | ARTsie creates them on first run. The token is a per-machine secret, so it is never committed. |

If step 4 fails with `Native MCP exited` or `Broken pipe`, an older ARTsie hub is still running from before the install. Stop it with `kill $(lsof -tiTCP:8743 -sTCP:LISTEN)` and run `./setup.sh` again. The next CLI call starts a fresh hub.

To move to newer ArtCraft releases, delete `downloads/<app>/release.json` and run `install_suite.py` again.

## What is here

| Location | Contents |
| --- | --- |
| `Applications/` | PhotoCraft, VectorCraft, FilmCraft, LightCraft, PdfCraft, EffectCraft, DesignCraft, FigCraft, WordCraft, SoundCraft, DeckCraft, CADCraft, GridCraft, and the official ArtCraft Launcher |
| `bin/` | One executable CLI link for each of the 13 editors |
| `sources/` | Editable source snapshots matching each installed release, including upstream licenses and documentation |
| `downloads/` | Original installers, CLI archives, source archives, release metadata, and published SHA-256 checksum files |
| `workspace/Inbox/` | Files copied into the studio |
| `workspace/Projects/` | Editable project files |
| `workspace/Exports/` | Finished copies and previews |
| `config/catalog.json` | Pinned installed versions, download provenance, and verified hashes |
| `config/mcp.json` | One MCP connection for the whole studio |
| `config/mcp-native-apps.json` | Optional direct connections to all 13 upstream MCP servers |
| `data/verification.json` | Native engine and gateway integration checks |
| `data/signatures.json` | Vendor bundle signature checks |

The upstream apps and engines are by the ArtCraft/storytold team, not newly reimplemented editors. ARTsie adds the hub, shared workspace, and gateway. The suite is early-stage software; tool availability and file compatibility differ by app.

## Use your files

1. Open **Files & folders** in ARTsie.
2. Use **Import file** or **Import folder** to copy something into Inbox. The original stays where it was.
3. Choose **Open with…** for a file, or open an app from **All apps**.
4. Save project files in Projects and exported copies in Exports.

The folder browser supports creating, renaming, moving, and copying within the workspace. It refuses overwriting an existing destination. It does not provide a delete action. Native editor save commands can overwrite files, so ask your LLM to work on copies.

## Connect an LLM

### Inside FD CODE

FD CODE's ARTsie integration gives its chat agents the `t3_artsie_*` tools automatically through the app's own MCP connection. `t3_artsie_cli` runs the unified CLI; the other tools offer app and file discovery, native calls, and live PhotoCraft/FilmCraft windows. Updated tools and instructions load when FD CODE's backend and provider session reload. The hub, CLI and native tool calls share the same persistent documents.

Ask FD CODE for the result you need, for example:

> Use ARTsie to copy my photo into Inbox, inspect it, make the changes I requested in PhotoCraft, and save a new export. Keep my original.

The ARTsie sidebar panel also opens apps, manages files and discovers tools. These controls run on the FD CODE host, including when the chat client is remote. Closing the panel leaves editing sessions running.

### Unified command line

Run `python3 scripts/install_cli.py` to install `~/.local/bin/artsie`. The installer uses the pinned dependencies in `cli/package-lock.json` and refreshes the native tool catalog. The command works from any project directory. It starts ARTsie's existing local service when necessary and never restarts an active service.

```sh
artsie apps --json
artsie search "crop" --json
artsie schema photocraft doc_export --json
artsie photocraft session_list --input '{}' --json
artsie call photocraft doc_export --input @/absolute/export-arguments.json --json
artsie import /absolute/input.png --json
artsie files Exports --json
```

Every installed app has a command group, with each discovered native operation exposed as a subcommand. `artsie <app> <tool> --input '{"argument":"value"}' --json` and `artsie call <app> <tool> ...` use the same execution path. Arguments are validated against the app's current schema before execution. `--input -` reads JSON from stdin. `artsie catalog refresh --json` updates discovery after native app updates; `--help`, `--schema --format json` and `--llms --format json` provide agent-readable command discovery.

Calls retain the document across CLI processes. Inspect a session before creating or opening a document, preserve unsaved work, and save new projects and exports under Projects and Exports. A failed call exits nonzero; a timeout has an unknown outcome and is not retried automatically. `artsie live photocraft --json` or `artsie live filmcraft --json` opens a separate visible agent window; use `--mode live` for its subsequent tools and calls. Other native tools use the supported headless sessions.

ARTsie supplies tools to an MCP-capable client; it does not include a chat model or require a new model API key. Your client supplies the LLM, model account, and its normal tool approvals. ARTsie does not upload files to an LLM itself; a connected client can send tool results to the model it uses.

### Codex

The project configuration is prepared in `.codex/config.toml`, following [official OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Reopen this folder in a new Codex session and trust the project through the client’s normal flow. Project configuration is loaded only for trusted folders. The running conversation’s tool list does not gain tools just because a config file was written.

Check the connection with `/mcp` in the client. If your client does not load project configurations, add the command from `config/mcp.json` in its MCP settings.

### Claude Code and other clients

`.mcp.json` contains the project connection for Claude Code. Open this folder in a fresh client session and enable the server through its normal MCP flow. For another client, merge the `artsie` entry from `config/mcp.json` into that client’s MCP configuration; keep its existing servers.

Start with:

> Use ARTsie to list my workspace files. Discover PhotoCraft’s tools, open a copy of my image, apply the adjustments I request, and save a new result in Exports. Preserve my original.

The gateway exposes:

- `artsie_apps`, `artsie_files`: inspect installed apps and shared files.
- `artsie_mkdir`, `artsie_copy`, `artsie_rename`: manage workspace files and folders.
- `artsie_launch`: open an installed desktop app, optionally with a workspace file.
- `artsie_tools`: get an app’s native tool names and exact argument schemas.
- `artsie_call`: call one of those native tools. Text and image results are forwarded.
- `artsie_start_live`: open a visible PhotoCraft or FilmCraft instance for live agent editing.

App IDs are lowercase, such as `photocraft`, `filmcraft`, and `soundcraft`. Discover the schema before calling a native tool. Native tool file paths should be absolute; folder tools take paths relative to `workspace/`.

### Headless and live editing

By default each app has a persistent **headless** engine. Its open document survives between calls while the service is running. These documents are separate from files open in an ordinary desktop editor. Save an export or project, then open it in the desktop app to review it.

For visible editing, ask:

> Start a live PhotoCraft window with ARTsie. Discover its tools, then use mode `live` for all calls while we work in that window.

Or select PhotoCraft/FilmCraft under **LLM connections** and click **Open live agent window**. The gateway and UI use the same local service and session. Live mode is implemented for those two editors; all 13 support headless mode. The other apps’ upstream documentation describes their own live connection options.

Closing the hub leaves the local service and editing sessions running, so an LLM session is not interrupted. Live desktop windows also remain open; close them normally when finished. Save your projects before restarting the Mac or stopping the service. Headless unsaved state is in memory, not a recovery database. `logs/` contains service and native MCP logs; the action log records tool names and outcomes rather than file contents.

### File access

The local HTTP service binds only to loopback and checks host, origin, and a per-run request token. The gateway’s folder operations stay inside `workspace/` and reject escaping paths and links.

Nine headless native servers support automation roots, enabled here for `workspace/`: PhotoCraft, VectorCraft, PdfCraft, EffectCraft, DesignCraft, FigCraft, WordCraft, SoundCraft, and DeckCraft. The installed FilmCraft, LightCraft, CADCraft, and GridCraft releases do not accept those flags and use the file permissions of your Mac account. The app catalog and connection panel show that distinction. PhotoCraft’s live window also has workspace roots and a private local control token; FilmCraft’s live channel is loopback-only with the upstream account-permission behavior. These file roots are not an OS process sandbox.

## Edit the apps or maintain the hub

Read the relevant `sources/<app>/AGENTS.md` and README before changing upstream source. Snapshots include source and licenses, but are not Git checkouts. The installed apps are the official prebuilt releases; modified source has not been compiled. Rust is needed to build your own native editor and is not installed by this setup. Upstream source can have optional build inputs such as fonts; follow its build documentation.

The hub uses Python 3.12+ with no pip dependencies, plus an AppKit/WebKit shell compiled using Swift. Rebuild its shell after changing `scripts/ARTsie.swift`:

```sh
python3 scripts/build_hub.py
```

The configured Python executable must remain installed. Run the hub directly for development with `python3 artsie.py serve`; run its gateway with `python3 artsie.py mcp`. Do not start a second service on port 8743. Restart the service after backend changes, after saving active work.

`scripts/install_suite.py` resumes the pinned official downloads from `downloads/*/release.json`. It verifies each Mac installer and CLI archive against the release’s SHA-256 list. It is a resumable installer, not an automatic updater, and does not replace existing app bundles. ArtCraft Launcher is included as the upstream updater; its own install/update operations normally target `/Applications`, so use it deliberately if you want system-wide installations. Keep ARTsie’s CLI and source versions aligned with its app catalog when updating this folder.

macOS File Provider adds empty FinderInfo metadata on this Desktop. Strict signature verification is therefore recorded against identical app files copied to temporary local staging without that metadata. Vendor signatures are preserved; the apps are not re-signed by ARTsie. The hub shell has a local ad-hoc signature.

## Verification

Run `python3 scripts/verify_cli.py` for all 13 CLI connections, exact-schema validation, a PhotoCraft edit/export with original preservation, safe imports, and a FilmCraft project saved across separate CLI invocations. It uses its own temporary hub and native documents. Results are stored in `data/cli-verification.json`.

Run `python3 scripts/verify_suite.py` to check all 13 native MCP servers, a PhotoCraft open/invert/export workflow with original preservation and workspace boundary refusal, an editable FilmCraft sequence/save workflow, and the client-facing stdio MCP bridge. The script creates clearly named test artifacts in Inbox, Projects, and Exports. It does not test every editor feature, codec, or output format. Live bridge and UI checks are recorded separately in `data/live-verification.json` and `data/http-verification.json` when available.
