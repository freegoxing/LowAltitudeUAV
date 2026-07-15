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
    useTopologyStore.getState().selectLink("l-2");
    assert.equal(useTopologyStore.getState().selectedLinkId, "l-2");
    assert.equal(useTopologyStore.getState().selectedNodeId, null);
    useTopologyStore.getState().clearSelection();
    assert.equal(useTopologyStore.getState().selectedLinkId, null);
});

test("topology layers and filters reset without changing domain data", () => {
    const originalNodes = useTopologyStore.getState().nodes;
    const originalLinks = useTopologyStore.getState().links;

    useTopologyStore.getState().toggleLayer("links");
    useTopologyStore.getState().setNodeTypes(["relay_drone"]);
    useTopologyStore.getState().setLinkStatuses(["degraded"]);
    assert.equal(useTopologyStore.getState().layers.links, false);
    assert.deepEqual(useTopologyStore.getState().filters.nodeTypes, ["relay_drone"]);

    useTopologyStore.getState().resetFilters();
    assert.deepEqual(useTopologyStore.getState().filters.nodeTypes, []);
    assert.deepEqual(useTopologyStore.getState().filters.linkStatuses, []);
    assert.equal(useTopologyStore.getState().nodes, originalNodes);
    assert.equal(useTopologyStore.getState().links, originalLinks);
});

test("connection statuses update independently", () => {
    useConnectionStore.getState().setApiStatus("disconnected");
    assert.equal(useConnectionStore.getState().apiStatus, "disconnected");
    assert.equal(useConnectionStore.getState().websocketStatus, "connected");
});
