import type {
    CommunicationLink,
    LinkStatus,
    LinkType,
    NodePriority,
    NodeStatus,
    RescueNode,
    RescueNodeType,
} from "@/types/rescue";

type RawUavNodeType = "GND-C" | "BS" | "UAV-R" | "UAV-M" | "GND-P" | "UAV-S";
type RawUavRelation =
    | "Link_BKH"
    | "Link_A2G"
    | "Link_A2A"
    | "Link_G2G"
    | "DISCONN";

interface RawUavNodeInput {
    id: string;
    name: string;
    type: string;
    desc: string;
    battery: number;
    capacity: number;
    snr_uplink: number;
    snr_downlink: number;
    connected_links_count: number;
}

interface RawUavEdgeInput {
    source: string;
    target: string;
    relation: string;
    snr: number;
    bandwidth: number;
}

export interface RawUavNetwork {
    nodes: RawUavNodeInput[];
    edges: RawUavEdgeInput[];
}

const NODE_TYPE_MAP: Record<RawUavNodeType, RescueNodeType> = {
    "GND-C": "command_vehicle",
    BS: "temporary_base_station",
    "UAV-R": "relay_drone",
    "UAV-M": "mission_drone",
    "GND-P": "rescue_team",
    "UAV-S": "communication_drone",
};

const TYPE_REGION_MAP: Record<RawUavNodeType, string> = {
    "GND-C": "指挥调度层",
    BS: "地面接入层",
    "UAV-R": "空中中继层",
    "UAV-M": "任务执行层",
    "GND-P": "地面救援终端",
    "UAV-S": "灾情侦察层",
};

const TYPE_COLUMN: Record<RawUavNodeType, number> = {
    "GND-C": 10,
    BS: 26,
    "UAV-R": 46,
    "UAV-M": 66,
    "GND-P": 86,
    "UAV-S": 58,
};

function statusFromNode(node: RawUavNode): NodeStatus {
    const snr = Math.min(node.snr_uplink, node.snr_downlink);
    if (node.battery < 0.48 || snr < 7) return "warning";
    if (node.capacity > 78 || node.connected_links_count >= 8) return "busy";
    return "online";
}

type RawUavNode = Omit<RawUavNodeInput, "type"> & { type: RawUavNodeType };
type RawUavEdge = Omit<RawUavEdgeInput, "relation"> & {
    relation: RawUavRelation;
};

function asRawUavNodeType(type: string): RawUavNodeType {
    if (type in NODE_TYPE_MAP) return type as RawUavNodeType;
    throw new Error(`Unsupported UAV node type: ${type}`);
}

function asRawUavRelation(relation: string): RawUavRelation {
    if (
        relation === "Link_BKH" ||
        relation === "Link_A2G" ||
        relation === "Link_A2A" ||
        relation === "Link_G2G" ||
        relation === "DISCONN"
    ) {
        return relation;
    }
    throw new Error(`Unsupported UAV link relation: ${relation}`);
}

function priorityFromNode(node: RawUavNode): NodePriority {
    if (node.type === "GND-C") return "P0";
    if (node.type === "BS" || node.type === "UAV-R") return "P1";
    return node.connected_links_count >= 6 ? "P1" : "P2";
}

function linkTypeFromRelation(relation: RawUavRelation): LinkType {
    if (relation === "DISCONN") return "emergency";
    if (relation === "Link_BKH") return "primary";
    if (relation === "Link_A2A") return "relay";
    return "backup";
}

function linkStatusFromEdge(edge: RawUavEdge): LinkStatus {
    if (edge.relation === "DISCONN" || edge.snr < 3) return "interrupted";
    if (edge.snr < 8) return "unstable";
    if (edge.snr < 13) return "degraded";
    return "normal";
}

function signalStrengthFromSnr(snr: number) {
    return Math.round(-92 + Math.min(30, snr) * 1.65);
}

function latencyFromSnr(snr: number, bandwidth: number) {
    return Math.round(12 + Math.max(0, 24 - snr) * 2.5 + 90 / Math.max(4, bandwidth));
}

function packetLossFromSnr(snr: number) {
    if (snr < 3) return 12;
    return Number(Math.max(0.2, 7.5 - snr * 0.45).toFixed(1));
}

function nodePosition(node: RawUavNode, indexByType: Map<RawUavNodeType, number>) {
    const index = indexByType.get(node.type) ?? 0;
    indexByType.set(node.type, index + 1);
    const rowOffset = node.type === "UAV-S" ? 12 : 0;

    return {
        x: TYPE_COLUMN[node.type],
        y: 14 + rowOffset + index * 8,
    };
}

export function adaptMockUavNodes(network: RawUavNetwork): RescueNode[] {
    const indexByType = new Map<RawUavNodeType, number>();
    const connectedNodeIdsByNode = new Map<string, Set<string>>();

    for (const edgeInput of network.edges) {
        const edge: RawUavEdge = {
            ...edgeInput,
            relation: asRawUavRelation(edgeInput.relation),
        };
        if (!connectedNodeIdsByNode.has(edge.source)) {
            connectedNodeIdsByNode.set(edge.source, new Set());
        }
        connectedNodeIdsByNode.get(edge.source)?.add(edge.target);
    }

    return network.nodes.map((nodeInput) => {
        const node: RawUavNode = {
            ...nodeInput,
            type: asRawUavNodeType(nodeInput.type),
        };
        const position = nodePosition(node, indexByType);
        const status = statusFromNode(node);

        return {
            id: node.id,
            name: node.name,
            type: NODE_TYPE_MAP[node.type],
            status,
            priority: priorityFromNode(node),
            position,
            longitude: 116.18 + TYPE_COLUMN[node.type] / 250,
            latitude: 40.04 + (position.y % 70) / 500,
            altitude: node.type.startsWith("UAV") ? 180 + node.capacity * 4 : undefined,
            battery: Math.round(node.battery * 100),
            signalStrength: signalStrengthFromSnr(node.snr_uplink),
            latency: latencyFromSnr(node.snr_uplink, node.capacity),
            bandwidth: node.capacity,
            packetLoss: packetLossFromSnr(node.snr_uplink),
            load: Math.min(
                96,
                Math.max(8, 100 - node.capacity + node.connected_links_count * 4),
            ),
            region: TYPE_REGION_MAP[node.type],
            connectedNodeIds: [...(connectedNodeIdsByNode.get(node.id) ?? [])],
            alertCount: status === "warning" ? 1 : 0,
            isCritical:
                node.type === "GND-C" || node.type === "BS" || node.type === "UAV-R",
            currentTask:
                node.type === "UAV-M" || node.type === "UAV-S" ? node.desc : undefined,
        };
    });
}

export function adaptMockUavLinks(network: RawUavNetwork): CommunicationLink[] {
    return network.edges.map((edgeInput, index) => {
        const edge: RawUavEdge = {
            ...edgeInput,
            relation: asRawUavRelation(edgeInput.relation),
        };
        const status = linkStatusFromEdge(edge);
        const type = linkTypeFromRelation(edge.relation);

        return {
            id: `uav-link-${index + 1}-${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type,
            status,
            priority:
                type === "primary" || status === "interrupted"
                    ? "critical"
                    : status === "normal"
                      ? "normal"
                      : "high",
            bandwidth: edge.bandwidth,
            latency: latencyFromSnr(edge.snr, edge.bandwidth),
            packetLoss: packetLossFromSnr(edge.snr),
            signalStrength: signalStrengthFromSnr(edge.snr),
            load: Math.min(96, Math.round(100 - edge.bandwidth / 6 + edge.snr)),
            isBackup: type === "backup",
            isCritical: type === "primary" || status === "interrupted",
        };
    });
}
