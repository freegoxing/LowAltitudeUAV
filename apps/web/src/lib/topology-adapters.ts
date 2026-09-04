import {
    hybridPosition,
    layoutTopology,
    mapPosition,
    mapPositions,
} from "@/lib/topology-layout";
import type { CommunicationLink, RescueNode } from "@/types/rescue";
import type {
    CommunicationFlowEdge,
    PathEmphasis,
    RescueFlowNode,
    TopologyAdaptOptions,
} from "@/types/topology";

type NodePosition = { x: number; y: number };

export function nearestHandles(source: NodePosition, target: NodePosition) {
    const deltaX = target.x - source.x;
    const deltaY = target.y - source.y;

    if (Math.abs(deltaX) >= Math.abs(deltaY)) {
        return deltaX >= 0
            ? { sourceHandle: "source-right", targetHandle: "target-left" }
            : { sourceHandle: "source-left", targetHandle: "target-right" };
    }

    return deltaY >= 0
        ? { sourceHandle: "source-bottom", targetHandle: "target-top" }
        : { sourceHandle: "source-top", targetHandle: "target-bottom" };
}

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
    const mappedPositions =
        options.mode === "map" ? mapPositions(positionedNodes) : null;
    const taskNodeIds = new Set(options.highlightedTaskNodeIds);
    const keyNodeIds = new Set(options.keyNodeIds ?? []);
    const nodeIds = new Set(positionedNodes.map((node) => node.id));
    const flowNodes = positionedNodes.map((node, index): RescueFlowNode => ({
        id: node.id,
        type: "rescueNode",
        position:
            options.mode === "topology"
                ? node.position
                : options.mode === "hybrid"
                  ? hybridPosition(node, index)
                  : mappedPositions?.get(node.id) ?? mapPosition(node),
        data: {
            rescueNode: node,
            dimmed: taskNodeIds.size > 0 && !taskNodeIds.has(node.id),
            isSubgraphKey: keyNodeIds.has(node.id),
            taskRoleLabel: options.nodeRoleLabels?.[node.id],
            visualPreference: options.mapVisualPreference,
            renderVariant: options.mode === "topology" ? "card" : "compact",
        },
        draggable: true,
    }));
    const positionsById = new Map(
        flowNodes.map((node) => [node.id, node.position]),
    );
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
        const handles = nearestHandles(
            positionsById.get(link.source)!,
            positionsById.get(link.target)!,
        );
        return [
            {
                id: link.id,
                source: link.source,
                target: link.target,
                type: "communicationLink",
                ...handles,
                data: {
                    link,
                    emphasis: getEmphasis(link, options),
                    isPrimaryPath: options.primaryLinkIds.includes(link.id),
                    isBackupPath: options.backupLinkIds.includes(link.id),
                    visualPreference: options.mapVisualPreference,
                },
                selectable: true,
            },
        ];
    });

    return { nodes: flowNodes, edges };
}
