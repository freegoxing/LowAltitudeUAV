import type { CommunicationLink, RescueNode } from "@/types/rescue";

export type SituationLevel = "L1" | "L2" | "L3";

export interface Agent1Assessment {
    level: SituationLevel;
    risk: "高" | "中" | "低";
    urgency: number;
    feasibility: number;
    summary: string;
}

export interface MissionFlowRequirement {
    id: string;
    source: string;
    receivers: string[];
    purpose: "搜救引导" | "医疗协同" | "态势同步";
    priority: number;
    latencyMs: number;
    reliability: number;
    deliveryMode: "anycast" | "multicast" | "unicast";
}

export interface MissionCommunicationSpecification {
    missionId: string;
    missionType: "人员搜救";
    missionPriority: "P0";
    keyNodeIds: string[];
    flows: MissionFlowRequirement[];
    resourceBudget: string;
    backupRequirement: string;
    healingPolicy: string;
}

export interface PlannedTaskSubgraph {
    missionId: string;
    keyNodeIds: string[];
    primaryLinkIds: string[];
    backupLinkIds: string[];
}

export interface AgentWorkflowDraft {
    message: string;
    assessment: Agent1Assessment;
    mcs: MissionCommunicationSpecification;
}

export const presetMissionPrompt = "立即搜救，重点保障医疗组并保持通信稳定";

const keyNodeIds = ["UAV-S-1", "GND-P-1", "UAV-M-3", "GND-C-1"];
function physicalLinkKey(link: CommunicationLink) {
    return [link.source, link.target].sort().join("|");
}

function shortestPathLinkIds(
    source: string,
    target: string,
    links: CommunicationLink[],
    blockedPhysicalLinks = new Set<string>(),
) {
    const queue: Array<{ nodeId: string; pathLinkIds: string[] }> = [{
        nodeId: source,
        pathLinkIds: [],
    }];
    const visited = new Set([source]);

    while (queue.length) {
        const current = queue.shift()!;
        if (current.nodeId === target) return current.pathLinkIds;

        for (const link of links) {
            if (
                blockedPhysicalLinks.has(physicalLinkKey(link))
                || (link.source !== current.nodeId && link.target !== current.nodeId)
            ) continue;
            const nextNodeId = link.source === current.nodeId ? link.target : link.source;
            if (visited.has(nextNodeId)) continue;
            visited.add(nextNodeId);
            queue.push({
                nodeId: nextNodeId,
                pathLinkIds: [...current.pathLinkIds, link.id],
            });
        }
    }

    return [];
}

function unique(ids: string[]) {
    return [...new Set(ids)];
}

export function createAgentWorkflowDraft(
    message: string,
    nodes: RescueNode[],
): AgentWorkflowDraft {
    const availableNodeIds = new Set(nodes.map((node) => node.id));
    const hasMedicalFocus = /医疗|救护|急救/.test(message);
    const assessment: Agent1Assessment = {
        level: "L1",
        risk: "高",
        urgency: 5,
        feasibility: 4,
        summary: "北坡救援链路存在弱化区，需优先维持告警与医疗协同的低时延高可靠传输。",
    };

    return {
        message,
        assessment,
        mcs: {
            missionId: "MCS-SAR-NORTH-01",
            missionType: "人员搜救",
            missionPriority: "P0",
            keyNodeIds: keyNodeIds.filter((id) => availableNodeIds.has(id)),
            flows: [
                {
                    id: "flow-search-guidance",
                    source: "UAV-S-1",
                    receivers: ["GND-P-1"],
                    purpose: "搜救引导",
                    priority: 5,
                    latencyMs: 80,
                    reliability: 0.99,
                    deliveryMode: "anycast",
                },
                {
                    id: "flow-medical-collaboration",
                    source: "UAV-S-1",
                    receivers: hasMedicalFocus ? ["UAV-M-3", "GND-P-1"] : ["GND-P-1"],
                    purpose: "医疗协同",
                    priority: hasMedicalFocus ? 5 : 4,
                    latencyMs: 120,
                    reliability: 0.98,
                    deliveryMode: "multicast",
                },
                {
                    id: "flow-command-summary",
                    source: "UAV-S-1",
                    receivers: ["GND-C-1"],
                    purpose: "态势同步",
                    priority: 3,
                    latencyMs: 300,
                    reliability: 0.95,
                    deliveryMode: "unicast",
                },
            ],
            resourceBudget: "语义带宽占用不超过 65%，最多启用 2 架中继无人机。",
            backupRequirement: "P0 业务流至少保留 1 条节点隔离备路径。",
            healingPolicy: "主链路 SNR 持续低于阈值时，在 150 ms 内切换备路径。",
        },
    };
}

export function planMissionSubgraph(
    mcs: MissionCommunicationSpecification,
    links: CommunicationLink[],
): PlannedTaskSubgraph {
    const primaryLinkIds = unique(mcs.flows.flatMap((flow) => {
        const paths = flow.receivers
            .map((receiver) => shortestPathLinkIds(flow.source, receiver, links))
            .filter((path) => path.length > 0)
            .sort((left, right) => left.length - right.length);
        return paths[0] ?? [];
    }));
    const primaryPhysicalLinks = new Set(
        links
            .filter((link) => primaryLinkIds.includes(link.id))
            .map(physicalLinkKey),
    );
    const backupLinkIds = unique(mcs.flows.flatMap((flow) => {
        const paths = flow.receivers
            .map((receiver) => shortestPathLinkIds(
                flow.source,
                receiver,
                links,
                primaryPhysicalLinks,
            ))
            .filter((path) => path.length > 0)
            .sort((left, right) => left.length - right.length);
        return paths[0] ?? [];
    }));

    return {
        missionId: mcs.missionId,
        keyNodeIds: mcs.keyNodeIds,
        primaryLinkIds,
        backupLinkIds,
    };
}
