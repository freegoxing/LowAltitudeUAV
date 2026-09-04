import type { RescueNode, RescueNodeType } from "@/types/rescue";

export type TopologyGroup = "command" | "infrastructure" | "airNetwork" | "mission" | "groundRescue" | "supportRisk";
export const topologyGroups = [
    { id: "command", label: "指挥调度", column: 0, row: 0 },
    { id: "infrastructure", label: "通信基础设施", column: 1, row: 0 },
    { id: "airNetwork", label: "空中通信网络", column: 2, row: 0 },
    { id: "mission", label: "任务无人机", column: 0, row: 1 },
    { id: "groundRescue", label: "地面救援力量", column: 1, row: 1 },
    { id: "supportRisk", label: "保障与风险目标", column: 2, row: 1 },
] as const;
const groupByType: Record<RescueNodeType, TopologyGroup> = { command_center: "command", command_vehicle: "command", satellite_terminal: "infrastructure", temporary_base_station: "infrastructure", relay_drone: "airNetwork", communication_drone: "airNetwork", mission_drone: "mission", rescue_team: "groundRescue", medical_point: "groundRescue", shelter: "supportRisk", trapped_area: "supportRisk" };
const typeOrder: Record<RescueNodeType, number> = { command_center: 0, command_vehicle: 1, satellite_terminal: 0, temporary_base_station: 1, relay_drone: 0, communication_drone: 1, mission_drone: 0, rescue_team: 0, medical_point: 1, shelter: 0, trapped_area: 1 };
const GROUP_WIDTH = 410, GROUP_HEIGHT = 650, GAP_X = 42, GAP_Y = 70, GRID_COLUMNS = 2, CELL_WIDTH = 180, CELL_HEIGHT = 116;
export function topologyGroupForType(type: RescueNodeType): TopologyGroup { return groupByType[type]; }
export function topologyGroupBounds(group: typeof topologyGroups[number]) { return { x: group.column * (GROUP_WIDTH + GAP_X), y: group.row * (GROUP_HEIGHT + GAP_Y), width: GROUP_WIDTH, height: GROUP_HEIGHT }; }
export function layoutTopology(nodes: RescueNode[]): RescueNode[] {
    const counts = new Map<TopologyGroup, number>();
    return [...nodes].sort((a, b) => {
        const groupOrder = topologyGroups.findIndex(g => g.id === topologyGroupForType(a.type)) - topologyGroups.findIndex(g => g.id === topologyGroupForType(b.type));
        return groupOrder || typeOrder[a.type] - typeOrder[b.type] || a.id.localeCompare(b.id);
    }).map(node => {
        const id = topologyGroupForType(node.type), group = topologyGroups.find(g => g.id === id)!;
        const index = counts.get(id) ?? 0; counts.set(id, index + 1);
        return { ...node, position: { x: group.column * (GROUP_WIDTH + GAP_X) + 28 + (index % GRID_COLUMNS) * CELL_WIDTH, y: group.row * (GROUP_HEIGHT + GAP_Y) + 62 + Math.floor(index / GRID_COLUMNS) * CELL_HEIGHT } };
    });
}
export function mapPosition(node: RescueNode) { return { x: node.position.x * 10, y: node.position.y * 10 }; }
export function hybridPosition(node: RescueNode, index: number) { const p = mapPosition(node), offset = (index % 3) * 8; return { x: p.x + offset, y: p.y - offset }; }
const viewport = { width: 1000, height: 720, paddingX: 48, paddingY: 56, compactNodeWidth: 80, compactNodeHeight: 38 };
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const scale = (value: number, min: number, max: number, start: number, end: number) => min === max ? (start + end) / 2 : start + ((value - min) / (max - min)) * (end - start);
export function mapPositions(nodes: RescueNode[]) {
    const positions = nodes.map(node => ({ id: node.id, x: node.position.x * 10, y: node.position.y * 10 }));
    const xs = positions.map(p => p.x), ys = positions.map(p => p.y), minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    return new Map(positions.map(p => [p.id, { x: clamp(scale(p.x, minX, maxX, viewport.paddingX, viewport.width - viewport.paddingX - viewport.compactNodeWidth), viewport.paddingX, viewport.width - viewport.paddingX - viewport.compactNodeWidth), y: clamp(scale(p.y, minY, maxY, viewport.paddingY, viewport.height - viewport.paddingY - viewport.compactNodeHeight), viewport.paddingY, viewport.height - viewport.paddingY - viewport.compactNodeHeight) }]));
}
