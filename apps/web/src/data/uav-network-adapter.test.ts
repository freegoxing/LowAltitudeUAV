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

test("places generated rescue assets around the Yingxiu mountain rescue scene", () => {
    const nodes = adaptMockUavNodes(rawNetwork);
    const commandVehicle = nodes.find((node) => node.id === "GND-C-1");

    assert.deepEqual(
        [commandVehicle?.latitude, commandVehicle?.longitude],
        [31.0607, 103.4858],
    );
    assert.ok(nodes.every((node) => node.latitude > 31.03 && node.latitude < 31.09));
    assert.ok(nodes.every((node) => node.longitude > 103.44 && node.longitude < 103.54));
});

test("distributes airborne assets across rescue corridors instead of type columns", () => {
    const nodes = adaptMockUavNodes(rawNetwork);
    const span = (values: number[]) => Math.max(...values) - Math.min(...values);
    const relayDrones = nodes.filter((node) => node.type === "relay_drone");
    const missionDrones = nodes.filter((node) => node.type === "mission_drone");
    const rescueTeams = nodes.filter((node) => node.type === "rescue_team");

    assert.ok(span(relayDrones.map((node) => node.longitude)) > 0.018);
    assert.ok(span(relayDrones.map((node) => node.latitude)) > 0.012);
    assert.ok(span(missionDrones.map((node) => node.longitude)) > 0.018);
    assert.ok(span(missionDrones.map((node) => node.latitude)) > 0.012);
    assert.ok(rescueTeams.some((node) => node.longitude > 103.5));
});
