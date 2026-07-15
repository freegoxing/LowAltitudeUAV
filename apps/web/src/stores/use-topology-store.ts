import { create } from "zustand";
import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import type { LayerVisibility, ViewMode } from "@/types/dashboard";
interface TopologyState { nodes: typeof mockNodes; links: typeof mockLinks; selectedNodeId: string | null; selectedLinkId: string | null; viewMode: ViewMode; layers: LayerVisibility; selectNode: (id: string) => void; selectLink: (id: string) => void; setViewMode: (mode: ViewMode) => void; toggleLayer: (key: keyof LayerVisibility) => void; }
export const useTopologyStore = create<TopologyState>((set) => ({ nodes: mockNodes, links: mockLinks, selectedNodeId: "n-relay", selectedLinkId: null, viewMode: "hybrid", layers: { nodes: true, links: true, tasks: true, risks: false, coverage: false }, selectNode: (selectedNodeId) => set({ selectedNodeId, selectedLinkId: null }), selectLink: (selectedLinkId) => set({ selectedLinkId, selectedNodeId: null }), setViewMode: (viewMode) => set({ viewMode }), toggleLayer: (key) => set((state) => ({ layers: { ...state.layers, [key]: !state.layers[key] } })) }));
