export type TopologyLegendItem = {
    id: "primary" | "backup" | "context" | "selectedLink" | "keyNode" | "selectedNode";
    label: string;
    symbolClass: string;
    nodeMarker?: boolean;
};

export const topologyLegendItems: TopologyLegendItem[] = [
    { id: "primary", label: "规划主路径", symbolClass: "primaryLine" },
    { id: "backup", label: "规划备用路径", symbolClass: "backupLine" },
    { id: "context", label: "背景可用链路", symbolClass: "contextLine" },
    { id: "selectedLink", label: "当前选中链路", symbolClass: "selectedLine" },
    { id: "keyNode", label: "子图关键节点", symbolClass: "keyNodeMarker", nodeMarker: true },
    { id: "selectedNode", label: "当前选中节点", symbolClass: "selectedNodeMarker", nodeMarker: true },
];
