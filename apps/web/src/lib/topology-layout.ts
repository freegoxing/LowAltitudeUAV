import type { RescueNode } from "@/types/rescue";

const TYPE_LEVEL: Record<RescueNode["type"], number> = {
    command_center: 0,
    command_vehicle: 0,
    satellite_terminal: 0,
    temporary_base_station: 1,
    communication_drone: 1,
    relay_drone: 1,
    mission_drone: 2,
    rescue_team: 2,
    medical_point: 2,
    shelter: 2,
    trapped_area: 3,
};

export function layoutTopology(nodes: RescueNode[]): RescueNode[] {
    const levelCounts = new Map<number, number>();

    return [...nodes]
        .sort((left, right) => left.id.localeCompare(right.id))
        .map((node) => {
            const level = TYPE_LEVEL[node.type];
            const index = levelCounts.get(level) ?? 0;
            levelCounts.set(level, index + 1);
            return {
                ...node,
                position: {
                    x: 140 + level * 250,
                    y: 120 + index * 170,
                },
            };
        });
}

export function mapPosition(node: RescueNode) {
    return { x: node.position.x * 10, y: node.position.y * 10 };
}

export function hybridPosition(node: RescueNode, index: number) {
    const offset = (index % 3) * 8;
    const position = mapPosition(node);
    return { x: position.x + offset, y: position.y - offset };
}

const MAP_VIEWPORT = {
    width: 1000,
    height: 720,
    paddingX: 48,
    paddingY: 56,
    compactNodeWidth: 80,
    compactNodeHeight: 38,
} as const;

function scaleToViewport(
    value: number,
    min: number,
    max: number,
    viewportStart: number,
    viewportEnd: number,
) {
    if (min === max) {
        return (viewportStart + viewportEnd) / 2;
    }
    return (
        viewportStart +
        ((value - min) / (max - min)) * (viewportEnd - viewportStart)
    );
}

function clamp(value: number, min: number, max: number) {
    return Math.min(max, Math.max(min, value));
}

export function mapPositions(nodes: RescueNode[]) {
    const basePositions = nodes.map((node) => ({
        id: node.id,
        x: node.position.x * 10,
        y: node.position.y * 10,
    }));
    const xValues = basePositions.map((position) => position.x);
    const yValues = basePositions.map((position) => position.y);
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    const map = new Map<string, { x: number; y: number }>();

    for (const position of basePositions) {
        map.set(position.id, {
            x: clamp(
                scaleToViewport(
                    position.x,
                    minX,
                    maxX,
                    MAP_VIEWPORT.paddingX,
                    MAP_VIEWPORT.width -
                        MAP_VIEWPORT.paddingX -
                        MAP_VIEWPORT.compactNodeWidth,
                ),
                MAP_VIEWPORT.paddingX,
                MAP_VIEWPORT.width -
                    MAP_VIEWPORT.paddingX -
                    MAP_VIEWPORT.compactNodeWidth,
            ),
            y: clamp(
                scaleToViewport(
                    position.y,
                    minY,
                    maxY,
                    MAP_VIEWPORT.paddingY,
                    MAP_VIEWPORT.height -
                        MAP_VIEWPORT.paddingY -
                        MAP_VIEWPORT.compactNodeHeight,
                ),
                MAP_VIEWPORT.paddingY,
                MAP_VIEWPORT.height -
                    MAP_VIEWPORT.paddingY -
                    MAP_VIEWPORT.compactNodeHeight,
            ),
        });
    }

    return map;
}
