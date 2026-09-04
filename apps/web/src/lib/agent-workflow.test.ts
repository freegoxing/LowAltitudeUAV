import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import {
    createAgentWorkflowDraft,
    planMissionSubgraph,
} from "./agent-workflow";

test("creates an MCS for a medical-priority rescue dialogue without routes", () => {
    const draft = createAgentWorkflowDraft(
        "立即搜救，重点保障医疗组并保持通信稳定",
        mockNodes,
    );

    assert.equal(draft.assessment.level, "L1");
    assert.deepEqual(draft.mcs.keyNodeIds, [
        "UAV-S-1",
        "GND-P-1",
        "GND-P-2",
        "GND-C-1",
    ]);
    assert.equal(draft.mcs.flows[0].purpose, "搜救引导");
    assert.equal("primaryLinkIds" in draft.mcs, false);
});

test("plans links only after receiving an MCS", () => {
    const draft = createAgentWorkflowDraft("立即搜救", mockNodes);
    const subgraph = planMissionSubgraph(draft.mcs, mockLinks);

    assert.ok(subgraph.primaryLinkIds.length >= 10);
    assert.ok(subgraph.backupLinkIds.length >= 7);
    assert.ok(subgraph.primaryLinkIds.every((id) => subgraph.links.some((link) => link.id === id)));
    assert.ok(subgraph.backupLinkIds.every((id) => subgraph.links.some((link) => link.id === id)));
});
