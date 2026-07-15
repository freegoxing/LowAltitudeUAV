export type ViewMode = "map" | "topology" | "hybrid";
export type ConsoleTab = "events" | "agent" | "rl" | "api";
export type ConnectionStatus = "connected" | "connecting" | "disconnected";
export type SimulationStatus = "idle" | "running" | "paused";
export interface LayerVisibility { nodes: boolean; links: boolean; tasks: boolean; risks: boolean; coverage: boolean; }
