import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "./mock-links";
import { mockNodes } from "./mock-nodes";
import { mockPlanningResult } from "./mock-planning-result";
import { mockTasks } from "./mock-tasks";
import { mockMissionSubgraphs } from "./mock-mission-subgraphs";

test("mock data has unique identifiers and valid relationships", () => {
    const nodeIds = new Set(mockNodes.map((node) => node.id));
    const linkIds = new Set(mockLinks.map((link) => link.id));

    assert.equal(nodeIds.size, mockNodes.length);
    assert.equal(linkIds.size, mockLinks.length);
    assert.ok(mockLinks.every((link) => nodeIds.has(link.source)));
    assert.ok(mockLinks.every((link) => nodeIds.has(link.target)));
    assert.ok(mockTasks.every((task) => task.progress >= 0 && task.progress <= 100));
    assert.ok(
        mockPlanningResult.criticalNodeIds.every((nodeId) => nodeIds.has(nodeId)),
    );
    assert.ok(
        mockPlanningResult.criticalLinkIds.every((linkId) => linkIds.has(linkId)),
    );
});

test("target-centric missions bind discovery nodes, action receivers, and planned subgraphs", () => {
    const nodeIds = new Set(mockNodes.map((node) => node.id));
    assert.ok(mockTasks.every((task) => nodeIds.has(task.target.discoveredBy)));
    assert.ok(mockTasks.every((task) => task.flows.every((flow) => nodeIds.has(flow.source))));
    assert.ok(mockTasks.every((task) => task.flows.some((flow) => flow.receivers.some((id) => id !== "GND-C-1"))));
    assert.ok(mockTasks.every((task) => mockMissionSubgraphs[task.id]));
});

test("rescue task copy identifies concrete locations around Yingxiu Town", () => {
    assert.deepEqual(
        mockTasks.map((task) => [
            task.id,
            task.name,
            task.target.positionLabel,
            task.region,
        ]),
        [
            [
                "t-1",
                "映秀镇老街北侧滑坡带失联人员搜救",
                "映秀镇老街北侧滑坡带",
                "映秀镇北侧救援区",
            ],
            [
                "t-2",
                "岷江河谷映秀镇东侧临时通信覆盖",
                "岷江河谷—映秀镇东侧通信盲区",
                "映秀镇东侧通信保障区",
            ],
            [
                "t-3",
                "映秀镇安置点医疗物资定点投送",
                "映秀镇安置点（213 国道沿线）",
                "映秀镇安置保障区",
            ],
            [
                "t-4",
                "漩口镇方向山体灾情侦察",
                "漩口镇方向山体风险区",
                "映秀镇西北侧侦察区",
            ],
        ],
    );
});

test("the default rescue mission visualizes the routing planner's selected subgraph", () => {
    const plannerKeyNodes = ["UAV-S-1", "GND-P-1", "GND-P-2", "GND-C-1"];
    const linkIds = new Set(mockLinks.map((link) => link.id));
    const plannedSubgraph = mockMissionSubgraphs["t-1"];

    assert.deepEqual(plannedSubgraph.primaryNodeIds, [
        "UAV-S-1",
        "UAV-R-7",
        "UAV-M-5",
        "GND-P-2",
        "UAV-M-4",
        "UAV-R-6",
        "UAV-R-1",
        "UAV-M-2",
        "GND-P-1",
        "BS-4",
        "GND-C-1",
    ]);
    assert.deepEqual(plannedSubgraph.keyNodeIds, plannerKeyNodes);
    assert.ok(plannedSubgraph.primaryLinkIds.length > 0);
    assert.ok(plannedSubgraph.primaryLinkIds.every((linkId) => linkIds.has(linkId)));
});
