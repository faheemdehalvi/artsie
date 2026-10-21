import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseInput } from "../src/client.ts";

test("keeps nested native JSON and shell metacharacters as data", async () => {
  const value = { path: "/Exports/a $(touch nope).png", params: { layers: [1, 2], enabled: false } };
  assert.deepEqual(await parseInput(JSON.stringify(value)), value);
});
test("accepts a JSON argument file with spaces in its name", async () => {
  const root = await mkdtemp(join(tmpdir(), "artsie-cli-input-"));
  try {
    const file = join(root, "native arguments.json");
    await writeFile(file, '{"width":160,"height":90}');
    assert.deepEqual(await parseInput("@" + file), { width: 160, height: 90 });
  } finally { await rm(root, { recursive: true }); }
});
test("rejects non-object native arguments", async () => {
  for (const input of ["null", "[]", "1", '"text"']) {
    await assert.rejects(parseInput(input), /JSON object/);
  }
  await assert.rejects(parseInput("{oops"), SyntaxError);
});
