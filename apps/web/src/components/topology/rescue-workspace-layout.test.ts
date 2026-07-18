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

test("keeps map background behind nodes and exposes visual preference styles", () => {
    assert.match(
        workspaceStyles,
        /\.react-flow__viewport-portal\)\s*{\s*z-index:0;/,
    );
    assert.match(workspaceStyles, /\.nodePriority\s*{[^}]*box-shadow:/);
    assert.match(workspaceStyles, /\.mapBackgroundSoft\s*{[^}]*opacity:/);
    assert.match(workspaceStyles, /\.visualModes\s*{[^}]*display:flex/);
});
