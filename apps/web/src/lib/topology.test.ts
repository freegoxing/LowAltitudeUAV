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
    assert.deepEqual(result.edges.map((edge) => edge.id), ["l-1", "l-2", "l-3"]);
    assert.deepEqual(result.nodes[0].position, { x: 500, y: 500 });
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

    assert.deepEqual(result.nodes.map((node) => node.id), ["n-relay"]);
    assert.deepEqual(result.links, []);
    assert.deepEqual(mockNodes, sourceNodes);
    assert.deepEqual(mockLinks, sourceLinks);
});

test("layout is deterministic and preserves input values", () => {
    const first = layoutTopology(mockNodes);
    const second = layoutTopology(mockNodes);

    assert.deepEqual(first, second);
    assert.notDeepEqual(first[0].position, mockNodes[0].position);
    assert.deepEqual(mockNodes[0].position, { x: 50, y: 50 });
});

test("edge emphasis follows selection, task, primary, backup priority", () => {
    const result = adaptTopology(mockNodes, mockLinks, {
        mode: "hybrid",
        selectedLinkId: "l-3",
        highlightedTaskNodeIds: ["n-relay", "n-team"],
        highlightedPathId: "path-main",
        primaryLinkIds: ["l-1", "l-2"],
        backupLinkIds: ["l-3"],
    });
    const emphasis = Object.fromEntries(
        result.edges.map((edge) => [edge.id, edge.data.emphasis]),
    );

    assert.deepEqual(emphasis, {
        "l-1": "task",
        "l-2": "task",
        "l-3": "selected",
    });
});
