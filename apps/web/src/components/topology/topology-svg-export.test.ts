import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("shows a topology-only SVG export action", () => {
    const source = readFileSync(
        new URL("./topology-toolbar.tsx", import.meta.url),
        "utf8",
    );

    assert.match(source, /导出 SVG/);
    assert.match(source, /createTopologySvg/);
});
