import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "./mock-links";
import { mockNodes } from "./mock-nodes";
import { mockPlanningResult } from "./mock-planning-result";
import { mockTasks } from "./mock-tasks";
import { mockMissionSubgraphs } from "./mock-mission-subgraphs";

test("mock data has unique identifiers and valid relationships", () => {
    const nodeIds = new Set(mockNodes.map((node) => node.id));
    const linkIds = new Set(mockLinks.map((link) => link.id));

    assert.equal(nodeIds.size, mockNodes.length);
    assert.equal(linkIds.size, mockLinks.length);
    assert.ok(mockLinks.every((link) => nodeIds.has(link.source)));
    assert.ok(mockLinks.every((link) => nodeIds.has(link.target)));
    assert.ok(mockTasks.every((task) => task.progress >= 0 && task.progress <= 100));
    assert.ok(
        mockPlanningResult.criticalNodeIds.every((nodeId) => nodeIds.has(nodeId)),
    );
    assert.ok(
        mockPlanningResult.criticalLinkIds.every((linkId) => linkIds.has(linkId)),
    );
});

test("target-centric missions bind discovery nodes, action receivers, and planned subgraphs", () => {
    const nodeIds = new Set(mockNodes.map((node) => node.id));
    assert.ok(mockTasks.every((task) => nodeIds.has(task.target.discoveredBy)));
    assert.ok(mockTasks.every((task) => task.flows.every((flow) => nodeIds.has(flow.source))));
    assert.ok(mockTasks.every((task) => task.flows.some((flow) => flow.receivers.some((id) => id !== "GND-C-1"))));
    assert.ok(mockTasks.every((task) => mockMissionSubgraphs[task.id]));
});
