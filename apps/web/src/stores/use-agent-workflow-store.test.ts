import assert from "node:assert/strict";
import test from "node:test";

import { useAgentWorkflowStore } from "./use-agent-workflow-store";

test("does not expose a planned subgraph until the MCS is confirmed", () => {
    useAgentWorkflowStore.getState().reset();
    useAgentWorkflowStore.getState().submitMessage("立即搜救，重点保障医疗组");

    assert.equal(useAgentWorkflowStore.getState().phase, "review");
    assert.equal(useAgentWorkflowStore.getState().plannedSubgraph, null);

    useAgentWorkflowStore.getState().confirmMission();

    assert.equal(useAgentWorkflowStore.getState().phase, "planned");
    assert.ok(useAgentWorkflowStore.getState().plannedSubgraph?.primaryLinkIds.length);
});
