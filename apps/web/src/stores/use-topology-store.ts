import { create } from "zustand";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import type { LayerVisibility, ViewMode } from "@/types/dashboard";
import type {
    LinkStatus,
    LinkType,
    NodeStatus,
    RescueNodeType,
} from "@/types/rescue";
import {
    defaultTopologyFilters,
    type TopologyFilters,
} from "@/types/topology";

interface TopologyState {
    nodes: typeof mockNodes;
    links: typeof mockLinks;
    selectedNodeId: string | null;
    selectedLinkId: string | null;
    viewMode: ViewMode;
    layers: LayerVisibility;
    filters: TopologyFilters;
    highlightedTaskId: string | null;
    highlightedPathId: string | null;
    viewRevision: number;
    centerRevision: number;
    selectNode: (id: string) => void;
    selectLink: (id: string) => void;
    clearSelection: () => void;
    setViewMode: (mode: ViewMode) => void;
    toggleLayer: (key: keyof LayerVisibility) => void;
    setNodeTypes: (types: RescueNodeType[]) => void;
    setNodeStatuses: (statuses: NodeStatus[]) => void;
    setLinkTypes: (types: LinkType[]) => void;
    setLinkStatuses: (statuses: LinkStatus[]) => void;
    resetFilters: () => void;
    highlightTask: (taskId: string | null, pathId?: string | null) => void;
    highlightPath: (pathId: string | null) => void;
    resetView: () => void;
    centerView: () => void;
}

const defaultLayers: LayerVisibility = {
    nodes: true,
    links: true,
    tasks: true,
    risks: false,
    coverage: false,
};

export const useTopologyStore = create<TopologyState>((set) => ({
    nodes: mockNodes,
    links: mockLinks,
    selectedNodeId: "UAV-R-5",
    selectedLinkId: null,
    viewMode: "hybrid",
    layers: defaultLayers,
    filters: defaultTopologyFilters,
    highlightedTaskId: "t-1",
    highlightedPathId: "path-main",
    viewRevision: 0,
    centerRevision: 0,
    selectNode: (selectedNodeId) => set({ selectedNodeId, selectedLinkId: null }),
    selectLink: (selectedLinkId) => set({ selectedLinkId, selectedNodeId: null }),
    clearSelection: () => set({ selectedNodeId: null, selectedLinkId: null }),
    setViewMode: (viewMode) => set({ viewMode }),
    toggleLayer: (key) =>
        set((state) => ({
            layers: { ...state.layers, [key]: !state.layers[key] },
        })),
    setNodeTypes: (nodeTypes) =>
        set((state) => ({ filters: { ...state.filters, nodeTypes }, selectedNodeId: null, selectedLinkId: null })),
    setNodeStatuses: (nodeStatuses) =>
        set((state) => ({ filters: { ...state.filters, nodeStatuses }, selectedNodeId: null, selectedLinkId: null })),
    setLinkTypes: (linkTypes) =>
        set((state) => ({ filters: { ...state.filters, linkTypes }, selectedNodeId: null, selectedLinkId: null })),
    setLinkStatuses: (linkStatuses) =>
        set((state) => ({ filters: { ...state.filters, linkStatuses }, selectedNodeId: null, selectedLinkId: null })),
    resetFilters: () => set({ filters: defaultTopologyFilters }),
    highlightTask: (highlightedTaskId, highlightedPathId = null) =>
        set({ highlightedTaskId, highlightedPathId }),
    highlightPath: (highlightedPathId) => set({ highlightedPathId }),
    resetView: () =>
        set((state) => ({ viewRevision: state.viewRevision + 1 })),
    centerView: () =>
        set((state) => ({ centerRevision: state.centerRevision + 1 })),
}));
