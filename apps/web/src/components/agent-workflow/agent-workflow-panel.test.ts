import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const panelSource = readFileSync(
    new URL("./agent-workflow-panel.tsx", import.meta.url),
    "utf8",
);
const sidebarSource = readFileSync(
    new URL("../layout/right-sidebar.tsx", import.meta.url),
    "utf8",
);
const planningSummarySource = readFileSync(
    new URL("../details/planning-summary.tsx", import.meta.url),
    "utf8",
);
const layoutStyles = readFileSync(
    new URL("../layout/workspace-layout.module.css", import.meta.url),
    "utf8",
);
const workflowStyles = readFileSync(
    new URL("./agent-workflow.module.css", import.meta.url),
    "utf8",
);

test("keeps topology planning behind an explicit MCS confirmation control", () => {
    assert.match(panelSource, /生成任务通信规范/);
    assert.match(panelSource, /确认并规划子图/);
    assert.match(panelSource, /submitMessage/);
    assert.match(panelSource, /confirmMission/);
    assert.match(panelSource, /Agent1 态势感知/);
    assert.match(panelSource, /Agent2 对话与任务翻译/);
    assert.match(panelSource, /AI 接口预留/);
});

test("mounts the agent workflow above planning details in the right sidebar", () => {
    assert.match(sidebarSource, /<AgentWorkflowPanel\s*\/>[\s\S]*<PlanningSummary/);
});

test("identifies an Agent2-confirmed subgraph in the planning summary", () => {
    assert.match(planningSummarySource, /useAgentWorkflowStore/);
    assert.match(planningSummarySource, /Agent2 已确认/);
});

test("keeps planning cards reachable by giving the agent panel a bounded scroll region", () => {
    assert.match(layoutStyles, /\.right\s*{[^}]*grid-template-rows:\s*auto minmax\(0,1fr\) auto[^}]*overflow:hidden[^}]*}/);
    assert.match(layoutStyles, /\.agentWorkflow\s*{[^}]*min-height:0[^}]*}/);
    assert.match(workflowStyles, /\.card\s*{[^}]*min-height:0[^}]*grid-template-rows:.*minmax\(0,1fr\)/);
    assert.match(workflowStyles, /\.body\s*{[^}]*min-height:0[^}]*overflow-y:auto/);
});

test("removes the warning list and dedicates its available height to the agent workspace", () => {
    assert.doesNotMatch(sidebarSource, /AlertList/);
    assert.match(sidebarSource, /<AgentWorkflowPanel\s*\/>[\s\S]*<PlanningSummary/);
});
