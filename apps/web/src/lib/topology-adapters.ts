import { hybridPosition, layoutTopology, mapPosition } from "@/lib/topology-layout";
import type { CommunicationLink, RescueNode } from "@/types/rescue";
import type {
    CommunicationFlowEdge,
    PathEmphasis,
    RescueFlowNode,
    TopologyAdaptOptions,
} from "@/types/topology";

function getEmphasis(
    link: CommunicationLink,
    options: TopologyAdaptOptions,
): PathEmphasis {
    if (link.id === options.selectedLinkId) return "selected";
    if (link.pathId && link.pathId === options.highlightedPathId) return "task";
    if (options.primaryLinkIds.includes(link.id)) return "primary";
    if (options.backupLinkIds.includes(link.id)) return "backup";
    return "muted";
}

export function adaptTopology(
    nodes: RescueNode[],
    links: CommunicationLink[],
    options: TopologyAdaptOptions,
): { nodes: RescueFlowNode[]; edges: CommunicationFlowEdge[] } {
    const positionedNodes =
        options.mode === "topology" ? layoutTopology(nodes) : nodes;
    const taskNodeIds = new Set(options.highlightedTaskNodeIds);
    const nodeIds = new Set(positionedNodes.map((node) => node.id));
    const flowNodes = positionedNodes.map((node, index): RescueFlowNode => ({
        id: node.id,
        type: "rescueNode",
        position:
            options.mode === "topology"
                ? node.position
                : options.mode === "hybrid"
                  ? hybridPosition(node, index)
                  : mapPosition(node),
        data: {
            rescueNode: node,
            dimmed: taskNodeIds.size > 0 && !taskNodeIds.has(node.id),
        },
        draggable: true,
    }));
    const edges = links.flatMap((link): CommunicationFlowEdge[] => {
        if (!nodeIds.has(link.source) || !nodeIds.has(link.target)) {
            if (process.env.NODE_ENV === "development") {
                console.warn("[topology] skipped link with missing endpoint", {
                    linkId: link.id,
                    source: link.source,
                    target: link.target,
                });
            }
            return [];
        }
        return [
            {
                id: link.id,
                source: link.source,
                target: link.target,
                type: "communicationLink",
                data: { link, emphasis: getEmphasis(link, options) },
                selectable: true,
            },
        ];
    });

    return { nodes: flowNodes, edges };
}
