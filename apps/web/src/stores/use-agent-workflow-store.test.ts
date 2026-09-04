import assert from "node:assert/strict";
import test from "node:test";

import { useAgentWorkflowStore } from "./use-agent-workflow-store";
import { presetMissionPrompt } from "@/lib/agent-workflow";

test("does not expose a planned subgraph until the MCS is confirmed", () => {
    useAgentWorkflowStore.getState().reset();
    useAgentWorkflowStore.getState().submitMessage(presetMissionPrompt);

    assert.equal(useAgentWorkflowStore.getState().phase, "review");
    assert.equal(useAgentWorkflowStore.getState().plannedSubgraph, null);

    useAgentWorkflowStore.getState().confirmMission();

    assert.equal(useAgentWorkflowStore.getState().phase, "planned");
    assert.ok(useAgentWorkflowStore.getState().plannedSubgraph?.primaryLinkIds.length);
});

test("reserves non-preset dialogue for a future AI integration", () => {
    useAgentWorkflowStore.getState().reset();
    useAgentWorkflowStore.getState().submitMessage("请评估河谷区域的通信风险");

    assert.equal(useAgentWorkflowStore.getState().phase, "awaiting_ai");
    assert.equal(useAgentWorkflowStore.getState().draft, null);
    assert.equal(useAgentWorkflowStore.getState().plannedSubgraph, null);
});
