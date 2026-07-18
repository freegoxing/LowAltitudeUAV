import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import { adaptTopology } from "@/lib/topology-adapters";
import { filterTopology } from "@/lib/topology-filters";
import { layoutTopology } from "@/lib/topology-layout";
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
    assert.deepEqual(result.nodes[0].position, {
        x: mockNodes[0].position.x * 10,
        y: mockNodes[0].position.y * 10,
    });
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

    assert.equal(emphasis.get("uav-link-21-BS-4-UAV-R-5"), "primary");
    assert.equal(emphasis.get("uav-link-59-UAV-R-5-UAV-M-3"), "primary");
    assert.equal(emphasis.get("uav-link-89-UAV-M-10-GND-P-2"), "selected");
    assert.equal(emphasis.get("uav-link-1-GND-C-1-BS-1"), "muted");
});
