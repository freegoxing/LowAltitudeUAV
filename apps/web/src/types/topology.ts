import type { Edge, Node } from "@xyflow/react";

import type {
    CommunicationLink,
    LinkStatus,
    LinkType,
    NodeStatus,
    RescueNode,
    RescueNodeType,
} from "@/types/rescue";

export type PathEmphasis =
    | "selected"
    | "task"
    | "primary"
    | "backup"
    | "muted";

export type RescueFlowNodeData = {
    rescueNode: RescueNode;
    dimmed: boolean;
};

export type CommunicationFlowEdgeData = {
    link: CommunicationLink;
    emphasis: PathEmphasis;
};

export type RescueFlowNode = Node<RescueFlowNodeData, "rescueNode">;
export type CommunicationFlowEdge = Edge<
    CommunicationFlowEdgeData,
    "communicationLink"
> & { data: CommunicationFlowEdgeData };

export interface TopologyFilters {
    nodeTypes: RescueNodeType[];
    nodeStatuses: NodeStatus[];
    linkTypes: LinkType[];
    linkStatuses: LinkStatus[];
}

export const defaultTopologyFilters: TopologyFilters = {
    nodeTypes: [],
    nodeStatuses: [],
    linkTypes: [],
    linkStatuses: [],
};

export interface TopologyAdaptOptions {
    mode: "map" | "topology" | "hybrid";
    selectedLinkId: string | null;
    highlightedTaskNodeIds: string[];
    highlightedPathId: string | null;
    primaryLinkIds: string[];
    backupLinkIds: string[];
}
