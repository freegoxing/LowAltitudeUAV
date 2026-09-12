import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import { adaptTopology, nearestHandles } from "@/lib/topology-adapters";
import { filterTopology } from "@/lib/topology-filters";
import { layoutTopology, topologyGroupForType, topologyGroups } from "@/lib/topology-layout";
import { topologyLegendItems } from "@/lib/topology-legend-data";
import type { CommunicationLink } from "@/types/rescue";
import { defaultTopologyFilters } from "@/types/topology";

test("adapts domain nodes and skips links with missing endpoints", () => {
    const invalidLink: CommunicationLink = {
        ...mockLinks[0],
        id: "invalid-link",
        target: "missing-node",
    };
    const result = adaptTopology(mockNodes, [...mockLinks, invalidLink], {
        mode: "map",
        selectedLinkId: null,
        highlightedTaskNodeIds: [],
        highlightedPathId: null,
        primaryLinkIds: ["l-1", "l-2"],
        backupLinkIds: ["l-3"],
    });

    assert.equal(result.nodes.length, mockNodes.length);
    assert.equal(result.edges.length, mockLinks.length);
    assert.ok(result.edges.every((edge) => edge.id !== "invalid-link"));
    assert.equal(result.nodes[0].data.renderVariant, "compact");
});

test("combines node and link filters without mutating source data", () => {
    const sourceNodes = structuredClone(mockNodes);
    const sourceLinks = structuredClone(mockLinks);
    const result = filterTopology(mockNodes, mockLinks, {
        ...defaultTopologyFilters,
        nodeTypes: ["relay_drone"],
        nodeStatuses: ["busy"],
        linkTypes: ["primary", "relay"],
        linkStatuses: ["degraded"],
    });

    assert.deepEqual(
        result.nodes.map((node) => node.id),
        ["UAV-R-2", "UAV-R-4", "UAV-R-5", "UAV-R-6"],
    );
    assert.ok(result.links.every((link) => link.status === "degraded"));
    assert.deepEqual(mockNodes, sourceNodes);
    assert.deepEqual(mockLinks, sourceLinks);
});

test("layout is deterministic and preserves input values", () => {
    const first = layoutTopology(mockNodes);
    const second = layoutTopology(mockNodes);

    assert.deepEqual(first, second);
    assert.notDeepEqual(first[0].position, mockNodes[0].position);
    assert.deepEqual(mockNodes[0].position, { x: 10, y: 14 });
});

test("topology layout groups assets in a stable two-by-three functional grid", () => {
    const layout = layoutTopology(mockNodes);
    const byId = new Map(layout.map((node) => [node.id, node]));

    assert.equal(topologyGroups.some((group) => group.id === "supportRisk"), false);
    assert.equal(topologyGroupForType("command_vehicle"), "command");
    assert.equal(topologyGroupForType("temporary_base_station"), "infrastructure");
    assert.equal(topologyGroupForType("relay_drone"), "airNetwork");
    assert.equal(topologyGroupForType("mission_drone"), "mission");
    assert.equal(topologyGroupForType("rescue_team"), "groundRescue");
    assert.ok(byId.get("GND-C-1")!.position.x < byId.get("BS-1")!.position.x);
    assert.ok(byId.get("BS-1")!.position.x < byId.get("UAV-R-1")!.position.x);
    assert.ok(byId.get("UAV-M-1")!.position.y > byId.get("UAV-R-1")!.position.y);
    assert.ok(byId.get("GND-P-1")!.position.x > byId.get("UAV-M-1")!.position.x);
    assert.deepEqual(layout, layoutTopology(mockNodes));
});

test("edge emphasis follows selection, task, primary, backup priority", () => {
    const result = adaptTopology(mockNodes, mockLinks, {
        mode: "hybrid",
        selectedLinkId: "uav-link-89-UAV-M-10-GND-P-2",
        highlightedTaskNodeIds: ["UAV-R-5", "UAV-M-3"],
        highlightedPathId: "path-main",
        primaryLinkIds: [
            "uav-link-21-BS-4-UAV-R-5",
            "uav-link-59-UAV-R-5-UAV-M-3",
        ],
        backupLinkIds: ["uav-link-89-UAV-M-10-GND-P-2"],
    });
    const emphasis = new Map(
        result.edges.map((edge) => [edge.id, edge.data.emphasis]),
    );
    const edges = new Map(result.edges.map((edge) => [edge.id, edge]));

    assert.equal(emphasis.get("uav-link-21-BS-4-UAV-R-5"), "primary");
    assert.equal(emphasis.get("uav-link-59-UAV-R-5-UAV-M-3"), "primary");
    assert.equal(emphasis.get("uav-link-89-UAV-M-10-GND-P-2"), "selected");
    assert.equal(emphasis.get("uav-link-1-GND-C-1-BS-1"), "muted");
    assert.equal(
        edges.get("uav-link-21-BS-4-UAV-R-5")?.data.isPrimaryPath,
        true,
    );
    assert.equal(
        edges.get("uav-link-89-UAV-M-10-GND-P-2")?.data.isBackupPath,
        true,
    );
});

test("topology edges use the nearest sides of their endpoint cards", () => {
    const result = adaptTopology(mockNodes, mockLinks, {
        mode: "topology",
        selectedLinkId: null,
        highlightedTaskNodeIds: [],
        highlightedPathId: null,
        primaryLinkIds: [],
        backupLinkIds: [],
        mapVisualPreference: "nodePriority",
    });
    const edge = result.edges.find(
        (item) => item.id === "uav-link-1-GND-C-1-BS-1",
    );

    assert.equal(edge?.sourceHandle, "source-right");
    assert.equal(edge?.targetHandle, "target-left");
});

test("nearest handles prefer the top and bottom sides for vertical paths", () => {
    assert.deepEqual(
        nearestHandles({ x: 100, y: 80 }, { x: 120, y: 360 }),
        { sourceHandle: "source-bottom", targetHandle: "target-top" },
    );
});

test("marks routing subgraph key nodes independently from normal task nodes", () => {
    const result = adaptTopology(mockNodes, mockLinks, {
        mode: "topology",
        selectedLinkId: null,
        highlightedTaskNodeIds: ["UAV-S-1", "UAV-R-7"],
        highlightedPathId: null,
        keyNodeIds: ["UAV-S-1"],
        primaryLinkIds: [],
        backupLinkIds: [],
        mapVisualPreference: "nodePriority",
    });
    const nodes = new Map(result.nodes.map((node) => [node.id, node]));

    assert.equal(nodes.get("UAV-S-1")!.data.isSubgraphKey, true);
    assert.equal(nodes.get("UAV-R-7")!.data.isSubgraphKey, false);
});

test("map mode keeps nodes inside the map viewport safe area", () => {
    const result = adaptTopology(mockNodes, mockLinks, {
        mode: "map",
        selectedLinkId: null,
        highlightedTaskNodeIds: [],
        highlightedPathId: null,
        primaryLinkIds: [],
        backupLinkIds: [],
        mapVisualPreference: "mapPriority",
    });
    const xValues = result.nodes.map((node) => node.position.x);
    const yValues = result.nodes.map((node) => node.position.y);

    assert.ok(Math.min(...xValues) >= 48);
    assert.ok(Math.max(...xValues) <= 912);
    assert.ok(Math.min(...yValues) >= 56);
    assert.ok(Math.max(...yValues) <= 664);
});

test("topology mode keeps the detailed card renderer", () => {
    const result = adaptTopology(mockNodes, mockLinks, {
        mode: "topology",
        selectedLinkId: null,
        highlightedTaskNodeIds: [],
        highlightedPathId: null,
        primaryLinkIds: [],
        backupLinkIds: [],
        mapVisualPreference: "nodePriority",
    });

    assert.equal(result.nodes[0].data.renderVariant, "card");
});

test("topology legend explains every planned path and highlight state", () => {
    assert.deepEqual(
        topologyLegendItems.map((item) => item.id),
        ["primary", "backup", "context", "selectedLink", "keyNode", "selectedNode"],
    );
});
