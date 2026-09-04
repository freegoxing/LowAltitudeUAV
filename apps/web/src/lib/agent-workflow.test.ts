import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import {
    createAgentWorkflowDraft,
    planMissionSubgraph,
    presetMissionPrompt,
} from "./agent-workflow";

test("creates an MCS for a medical-priority rescue dialogue without routes", () => {
    const draft = createAgentWorkflowDraft(
        "立即搜救，重点保障医疗组并保持通信稳定",
        mockNodes,
    );

    assert.equal(draft.assessment.level, "L1");
    assert.equal(draft.mcs.candidateGroups.length, 4);
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

test("labels the preset medical receiver with its mission role", () => {
    const draft = createAgentWorkflowDraft(presetMissionPrompt, mockNodes);
    const subgraph = planMissionSubgraph(draft.mcs, mockLinks);

    assert.equal(subgraph.nodeRoleLabels["GND-P-2"], "医疗组");
    assert.equal(subgraph.nodeRoleLabels["UAV-S-1"], "侦察感知");
    assert.equal(subgraph.nodeRoleLabels["GND-P-1"], "搜救组");
    assert.equal(subgraph.nodeRoleLabels["GND-C-1"], "指挥中心");
});

test("keeps multiple communication-node candidates inside each mission tag before planning", () => {
    const draft = createAgentWorkflowDraft(presetMissionPrompt, mockNodes);
    const medicalGroup = draft.mcs.candidateGroups.find((group) => group.label === "医疗组");

    assert.deepEqual(medicalGroup?.nodeIds, ["GND-P-2", "UAV-M-4", "UAV-M-5", "UAV-R-6"]);
    assert.equal(draft.mcs.candidateGroups.every((group) => group.nodeIds.length > 1), true);
});
