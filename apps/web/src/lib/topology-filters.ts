import type { CommunicationLink, RescueNode } from "@/types/rescue";
import type { TopologyFilters } from "@/types/topology";

export function filterTopology(
    nodes: RescueNode[],
    links: CommunicationLink[],
    filters: TopologyFilters,
) {
    const filteredNodes = nodes.filter(
        (node) =>
            (!filters.nodeTypes.length || filters.nodeTypes.includes(node.type)) &&
            (!filters.nodeStatuses.length ||
                filters.nodeStatuses.includes(node.status)),
    );
    const visibleNodeIds = new Set(filteredNodes.map((node) => node.id));
    const filteredLinks = links.filter(
        (link) =>
            visibleNodeIds.has(link.source) &&
            visibleNodeIds.has(link.target) &&
            (!filters.linkTypes.length || filters.linkTypes.includes(link.type)) &&
            (!filters.linkStatuses.length ||
                filters.linkStatuses.includes(link.status)),
    );

    return { nodes: filteredNodes, links: filteredLinks };
}
