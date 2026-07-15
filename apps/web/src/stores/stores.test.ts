import assert from "node:assert/strict";
import test from "node:test";
import { useDashboardStore } from "./use-dashboard-store";
import { useTopologyStore } from "./use-topology-store";
import { useConnectionStore } from "./use-connection-store";

test("dashboard and topology actions update focused state", () => {
    useDashboardStore.getState().setConsoleTab("agent");
    assert.equal(useDashboardStore.getState().consoleTab, "agent");
    useTopologyStore.getState().selectNode("n-relay");
    assert.equal(useTopologyStore.getState().selectedNodeId, "n-relay");
    assert.equal(useTopologyStore.getState().selectedLinkId, null);
});

test("connection statuses update independently", () => {
    useConnectionStore.getState().setApiStatus("disconnected");
    assert.equal(useConnectionStore.getState().apiStatus, "disconnected");
    assert.equal(useConnectionStore.getState().websocketStatus, "connected");
});
