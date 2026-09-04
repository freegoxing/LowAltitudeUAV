import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
    new URL("./topology-canvas.tsx", import.meta.url),
    "utf8",
);

test("prefers an explicitly confirmed Agent2 subgraph over the selected task fixture", () => {
    assert.match(source, /useAgentWorkflowStore/);
    assert.match(source, /plannedSubgraph \?\? taskSubgraph/);
    assert.match(source, /keyNodeIds: activeSubgraph\?\.keyNodeIds/);
    assert.match(source, /primaryLinkIds: activeSubgraph\?\.primaryLinkIds \?\? \[\]/);
    assert.match(source, /backupLinkIds: activeSubgraph\?\.backupLinkIds \?\? \[\]/);
});

test("clears selected-task node highlights when an Agent2 subgraph is confirmed", () => {
    assert.match(source, /const selectedTaskNodeIds = plannedSubgraph \? \[\] : \[/);
    assert.match(source, /\.\.\.selectedTaskNodeIds/);
});
