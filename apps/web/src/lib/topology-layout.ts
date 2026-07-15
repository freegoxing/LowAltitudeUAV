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
