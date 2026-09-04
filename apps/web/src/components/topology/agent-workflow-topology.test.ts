import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
    new URL("./topology-canvas.tsx", import.meta.url),
    "utf8",
);

test("uses an explicitly confirmed Agent2 subgraph for topology emphasis", () => {
    assert.match(source, /useAgentWorkflowStore/);
    assert.match(source, /keyNodeIds: plannedSubgraph\?\.keyNodeIds/);
    assert.match(source, /primaryLinkIds: plannedSubgraph\?\.primaryLinkIds \?\? \[\]/);
    assert.match(source, /backupLinkIds: plannedSubgraph\?\.backupLinkIds \?\? \[\]/);
});

test("does not highlight task nodes before an Agent2 subgraph is confirmed", () => {
    assert.match(source, /if \(!state\.layers\.tasks \|\| !plannedSubgraph\) return \[\];/);
    assert.doesNotMatch(source, /mockMissionSubgraphs/);
    assert.doesNotMatch(source, /mockTasks/);
});

test("renders communication links only after a mission subgraph is confirmed", () => {
    assert.match(source, /const plannedLinks = useMemo\(/);
    assert.match(source, /plannedSubgraph\?\.links \?\? \[\]/);
    assert.match(source, /adaptTopology\(filtered\.nodes, plannedLinks/);
    assert.match(source, /links=\{plannedLinks\}/);
});
