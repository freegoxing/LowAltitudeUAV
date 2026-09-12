import { topologyGroupForType, topologyGroups } from "@/lib/topology-layout";
import type {
    CommunicationFlowEdge,
    PathEmphasis,
    RescueFlowNode,
} from "@/types/topology";

const canvas = { width: 1500, height: 500 };
const group = { width: 470, height: 215, gapX: 20, gapY: 20, margin: 20 };
const card = { width: 100, height: 45 };

type Point = { x: number; y: number };

const xml = (value: string | number) => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");

function exportPositions(nodes: RescueFlowNode[]) {
    const grouped = new Map(topologyGroups.map((item) => [item.id, [] as RescueFlowNode[]]));
    nodes.forEach((node) => grouped.get(topologyGroupForType(node.data.rescueNode.type))?.push(node));

    return new Map(nodes.map((node) => {
        const groupId = topologyGroupForType(node.data.rescueNode.type);
        const definition = topologyGroups.find((item) => item.id === groupId)!;
        const index = grouped.get(groupId)!.findIndex((item) => item.id === node.id);
        return [node.id, {
            x: group.margin + definition.column * (group.width + group.gapX) + 14 + (index % 4) * 112,
            y: group.margin + definition.row * (group.height + group.gapY) + 40 + Math.floor(index / 4) * 55,
        }];
    }));
}

function lineStyle(emphasis: PathEmphasis, type: CommunicationFlowEdge["data"]["link"]["type"]) {
    if (emphasis === "selected") return { color: "#1d4ed8", width: 3, dash: "" };
    if (emphasis === "primary" || emphasis === "task") return { color: "#f43f5e", width: 2.6, dash: "" };
    if (emphasis === "backup") return { color: "#f59e0b", width: 2.4, dash: "7 4" };
    return { color: type === "emergency" ? "#dc4c4c" : "#94a3b8", width: 1.2, dash: "" };
}

function linkPath(source: Point, target: Point) {
    const sourceCenter = { x: source.x + card.width / 2, y: source.y + card.height / 2 };
    const targetCenter = { x: target.x + card.width / 2, y: target.y + card.height / 2 };
    const horizontal = Math.abs(targetCenter.x - sourceCenter.x) >= Math.abs(targetCenter.y - sourceCenter.y);
    const sourceEnd = horizontal
        ? { x: sourceCenter.x + Math.sign(targetCenter.x - sourceCenter.x) * card.width / 2, y: sourceCenter.y }
        : { x: sourceCenter.x, y: sourceCenter.y + Math.sign(targetCenter.y - sourceCenter.y) * card.height / 2 };
    const targetEnd = horizontal
        ? { x: targetCenter.x - Math.sign(targetCenter.x - sourceCenter.x) * card.width / 2, y: targetCenter.y }
        : { x: targetCenter.x, y: targetCenter.y - Math.sign(targetCenter.y - sourceCenter.y) * card.height / 2 };
    const offset = horizontal
        ? Math.max(24, Math.abs(targetEnd.x - sourceEnd.x) * 0.28)
        : Math.max(24, Math.abs(targetEnd.y - sourceEnd.y) * 0.35);
    const direction = horizontal
        ? Math.sign(targetEnd.x - sourceEnd.x)
        : Math.sign(targetEnd.y - sourceEnd.y);
    const sourceControl = horizontal
        ? { x: sourceEnd.x + direction * offset, y: sourceEnd.y }
        : { x: sourceEnd.x, y: sourceEnd.y + direction * offset };
    const targetControl = horizontal
        ? { x: targetEnd.x - direction * offset, y: targetEnd.y }
        : { x: targetEnd.x, y: targetEnd.y - direction * offset };
    return `M ${sourceEnd.x} ${sourceEnd.y} C ${sourceControl.x} ${sourceControl.y}, ${targetControl.x} ${targetControl.y}, ${targetEnd.x} ${targetEnd.y}`;
}

export function createTopologySvg(nodes: RescueFlowNode[], edges: CommunicationFlowEdge[]): string {
    const positions = exportPositions(nodes);
    const groups = topologyGroups.map((item) => {
        const x = group.margin + item.column * (group.width + group.gapX);
        const y = group.margin + item.row * (group.height + group.gapY);
        return `<g class="topology-group"><rect x="${x}" y="${y}" width="${group.width}" height="${group.height}" rx="12" fill="#f8fafc" stroke="#cbd5e1"/><text x="${x + 14}" y="${y + 25}" fill="#475569" font-size="13" font-weight="700">${xml(item.label)}</text></g>`;
    }).join("");
    const links = edges.flatMap((edge) => {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) return [];
        const style = lineStyle(edge.data.emphasis, edge.data.link.type);
        return `<path class="topology-link" d="${linkPath(source, target)}" fill="none" stroke="${style.color}" stroke-width="${style.width}"${style.dash ? ` stroke-dasharray="${style.dash}"` : ""} opacity="${edge.data.emphasis === "muted" ? "0.55" : "1"}"/>`;
    }).join("");
    const nodeCards = nodes.map((node) => {
        const position = positions.get(node.id)!;
        const rescueNode = node.data.rescueNode;
        const border = node.data.isSubgraphKey ? "#f5b700" : "#cbd5e1";
        const fill = node.data.dimmed ? "#f8fafc" : "#ffffff";
        const status = rescueNode.status === "online" ? "在线" : rescueNode.status === "busy" ? "忙碌" : rescueNode.status === "warning" ? "告警" : "离线";
        return `<g class="topology-node"><rect class="topology-node" x="${position.x}" y="${position.y}" width="${card.width}" height="${card.height}" rx="7" fill="${fill}" stroke="${border}"${node.data.isSubgraphKey ? " stroke-width=\"2\"" : ""}/><text x="${position.x + 8}" y="${position.y + 18}" fill="#1e293b" font-size="10" font-weight="700">${xml(rescueNode.name)}</text><text x="${position.x + 8}" y="${position.y + 34}" fill="#64748b" font-size="8">${xml(status)} · ${rescueNode.battery != null ? `电量 ${rescueNode.battery}%` : `${rescueNode.load}% 负载`}</text></g>`;
    }).join("");

    return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}"><title>低空应急救援通信拓扑</title><rect width="100%" height="100%" fill="#ffffff"/>${groups}${links}${nodeCards}</svg>`;
}
