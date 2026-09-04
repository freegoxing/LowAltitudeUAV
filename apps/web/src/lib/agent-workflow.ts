import type { CommunicationLink, RescueNode } from "@/types/rescue";
import presetPlannerOutput from "@/data/generated-task-communication-subgraph.json";

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

export interface MissionCandidateGroup {
    id: string;
    label: string;
    nodeIds: string[];
}

export interface MissionCommunicationSpecification {
    missionId: string;
    missionType: "人员搜救";
    missionPriority: "P0";
    candidateGroups: MissionCandidateGroup[];
    flows: MissionFlowRequirement[];
    resourceBudget: string;
    backupRequirement: string;
    healingPolicy: string;
}

export interface PlannedTaskSubgraph {
    missionId: string;
    keyNodeIds: string[];
    nodeRoleLabels: Record<string, string>;
    primaryLinkIds: string[];
    backupLinkIds: string[];
    links: CommunicationLink[];
}

export interface AgentWorkflowDraft {
    message: string;
    assessment: Agent1Assessment;
    mcs: MissionCommunicationSpecification;
}

export const presetMissionPrompt = "立即搜救，重点保障医疗组并保持通信稳定";

function latencyMs(value: string) {
    const parsed = Number.parseFloat(value);
    return value.includes("s") && !value.includes("ms") ? parsed * 1000 : parsed;
}

function plannedLinksForPaths(
    paths: string[][],
    pathType: "primary" | "backup",
    availableLinks: CommunicationLink[],
) {
    return paths.flatMap((path, pathIndex) => path.slice(1).map((target, hopIndex) => {
        const source = path[hopIndex];
        const existing = availableLinks.find((link) => (
            (link.source === source && link.target === target)
            || (link.source === target && link.target === source)
        ));
        return {
            id: `preset-${pathType}-${pathIndex}-${hopIndex}-${source}-${target}`,
            source,
            target,
            type: pathType,
            status: existing?.status ?? "normal",
            priority: pathType === "primary" ? "critical" : "high",
            bandwidth: existing?.bandwidth ?? 24,
            latency: existing?.latency ?? 36,
            packetLoss: existing?.packetLoss ?? 0.6,
            signalStrength: existing?.signalStrength ?? -68,
            load: existing?.load ?? 42,
            isBackup: pathType === "backup",
            isCritical: pathType === "primary",
        } satisfies CommunicationLink;
    }));
}

function missionNodeRoleLabels(mcs: MissionCommunicationSpecification) {
    const labels: Record<string, string> = {};
    const receiverRoleByPurpose: Record<MissionFlowRequirement["purpose"], string> = {
        "搜救引导": "搜救组",
        "医疗协同": "医疗组",
        "态势同步": "指挥中心",
    };

    for (const flow of mcs.flows) {
        if (flow.source.startsWith("UAV-S")) labels[flow.source] = "侦察感知";
        for (const receiver of flow.receivers) {
            labels[receiver] = receiverRoleByPurpose[flow.purpose];
        }
    }

    return labels;
}

export function createAgentWorkflowDraft(
    message: string,
    nodes: RescueNode[],
): AgentWorkflowDraft {
    const availableNodeIds = new Set(nodes.map((node) => node.id));
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
            missionId: presetPlannerOutput.mission.mission_id,
            missionType: "人员搜救",
            missionPriority: "P0",
            candidateGroups: presetPlannerOutput.mission.candidate_groups.map((group) => ({
                id: group.group_id,
                label: group.label,
                nodeIds: group.node_ids.filter((id) => availableNodeIds.has(id)),
            })),
            flows: presetPlannerOutput.mission.mission_flows.map((flow) => ({
                id: flow.flow_id,
                source: flow.source,
                receivers: flow.receivers,
                purpose: flow.purpose as MissionFlowRequirement["purpose"],
                priority: flow.priority,
                latencyMs: latencyMs(flow.latency_req),
                reliability: flow.reliability_req,
                deliveryMode: flow.delivery_mode as MissionFlowRequirement["deliveryMode"],
            })),
            resourceBudget: "预设模型结果：带宽上限 70%，中继数上限 3，功率上限 +3 dB。",
            backupRequirement: "预设模型结果：P5 业务需要 2 条备路，P4 业务需要 1 条备路。",
            healingPolicy: "预设模型结果：SNR 低于 8 dB 时自动切换，延迟低于 500 ms。",
        },
    };
}

export function planMissionSubgraph(
    mcs: MissionCommunicationSpecification,
    links: CommunicationLink[],
): PlannedTaskSubgraph {
    const primaryLinks = plannedLinksForPaths(
        presetPlannerOutput.flow_results.map((result) => result.primary_path),
        "primary",
        links,
    );
    const backupLinks = plannedLinksForPaths(
        presetPlannerOutput.flow_results.flatMap((result) => result.backup_paths),
        "backup",
        links,
    );

    return {
        missionId: mcs.missionId,
        keyNodeIds: presetPlannerOutput.selected_key_nodes
            ?? presetPlannerOutput.mission.key_nodes,
        nodeRoleLabels: missionNodeRoleLabels(mcs),
        primaryLinkIds: primaryLinks.map((link) => link.id),
        backupLinkIds: backupLinks.map((link) => link.id),
        links: [...primaryLinks, ...backupLinks],
    };
}
