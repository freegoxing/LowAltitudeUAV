import assert from "node:assert/strict";
import test from "node:test";

import rawNetwork from "../../../../data/mock_uav_network.json";
import {
    adaptMockUavLinks,
    adaptMockUavNodes,
} from "./uav-network-adapter";

test("loads generated UAV network nodes into rescue topology data", () => {
    const nodes = adaptMockUavNodes(rawNetwork);

    assert.equal(nodes.length, rawNetwork.nodes.length);
    assert.ok(nodes.length > 20);
    assert.ok(nodes.some((node) => node.id === "GND-C-1"));
    assert.ok(nodes.some((node) => node.type === "relay_drone"));
    assert.ok(nodes.every((node) => Number.isFinite(node.position.x)));
    assert.ok(nodes.every((node) => Number.isFinite(node.position.y)));
});

test("loads generated UAV communication edges with valid endpoints", () => {
    const nodes = adaptMockUavNodes(rawNetwork);
    const links = adaptMockUavLinks(rawNetwork);
    const nodeIds = new Set(nodes.map((node) => node.id));

    assert.equal(links.length, rawNetwork.edges.length);
    assert.ok(links.length > nodes.length);
    assert.ok(links.every((link) => nodeIds.has(link.source)));
    assert.ok(links.every((link) => nodeIds.has(link.target)));
    assert.ok(links.some((link) => link.status === "interrupted"));
});
