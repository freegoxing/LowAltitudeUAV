import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspaceStyles = readFileSync(
    new URL("./rescue-workspace.module.css", import.meta.url),
    "utf8",
);
const layoutStyles = readFileSync(
    new URL("../layout/workspace-layout.module.css", import.meta.url),
    "utf8",
);

test("passes the center grid height through to the React Flow canvas", () => {
    assert.match(
        layoutStyles,
        /\.center\s*{[^}]*display:grid[^}]*min-height:0[^}]*}/,
    );
    assert.match(workspaceStyles, /\.workspace\s*{[^}]*height:100%[^}]*}/);
    assert.match(
        workspaceStyles,
        /\.canvas\s*{[^}]*min-height:0[^}]*overflow:hidden[^}]*}/,
    );
});
