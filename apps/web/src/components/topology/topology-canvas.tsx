"use client";

import { useEffect, useMemo, useRef } from "react";
import {
    Background,
    BackgroundVariant,
    Controls,
    ReactFlow,
    ViewportPortal,
    useEdgesState,
    useNodesState,
    useReactFlow,
} from "@xyflow/react";

import { mockPlanningResult } from "@/data/mock-planning-result";
import { mockTasks } from "@/data/mock-tasks";
import { adaptTopology } from "@/lib/topology-adapters";
import { filterTopology } from "@/lib/topology-filters";
import { useTopologyStore } from "@/stores/use-topology-store";
import type { ViewMode } from "@/types/dashboard";
import type { CommunicationFlowEdge, RescueFlowNode } from "@/types/topology";
import { CommunicationEdge } from "./communication-edge";
import { MapBackground } from "./map-background";
import { RescueNode } from "./rescue-node";
import { TopologyLegend } from "./topology-legend";
import styles from "./rescue-workspace.module.css";

const nodeTypes = { rescueNode: RescueNode };
const edgeTypes = { communicationLink: CommunicationEdge };
const fitOptions = { padding: 0.22, maxZoom: 1.35 };

interface SceneProps {
    incomingNodes: RescueFlowNode[];
    incomingEdges: CommunicationFlowEdge[];
    mode: ViewMode;
    viewRevision: number;
    centerRevision: number;
}

function TopologyScene({ incomingNodes, incomingEdges, mode, viewRevision, centerRevision }: SceneProps) {
    const state = useTopologyStore();
    const [nodes, setNodes, onNodesChange] = useNodesState(incomingNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(incomingEdges);
    const { fitView } = useReactFlow();
    const previousMode = useRef(mode);
    const previousViewRevision = useRef(viewRevision);

    useEffect(() => {
        const shouldResetPositions = previousMode.current !== mode || previousViewRevision.current !== viewRevision;
        previousMode.current = mode;
        previousViewRevision.current = viewRevision;
        setNodes((currentNodes) => incomingNodes.map((node) => ({
            ...node,
            position: shouldResetPositions
                ? node.position
                : currentNodes.find((current) => current.id === node.id)?.position ?? node.position,
        })));
        setEdges(incomingEdges);
        if (shouldResetPositions) requestAnimationFrame(() => void fitView(fitOptions));
    }, [incomingEdges, incomingNodes, mode, viewRevision, fitView, setEdges, setNodes]);

    useEffect(() => {
        if (centerRevision > 0) requestAnimationFrame(() => void fitView(fitOptions));
    }, [centerRevision, fitView]);

    return (
        <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={fitOptions}
            minZoom={0.35}
            maxZoom={2}
            nodesDraggable
            onNodeClick={(_, node) => state.selectNode(node.id)}
            onEdgeClick={(_, edge) => state.selectLink(edge.id)}
            onPaneClick={state.clearSelection}
            proOptions={{ hideAttribution: true }}
            colorMode="light"
        >
            <ViewportPortal>
                {mode !== "topology" && (
                    <div className={styles.mapViewport}>
                        <MapBackground
                            muted={mode === "hybrid"}
                            showRisks={state.layers.risks}
                            showCoverage={state.layers.coverage}
                        />
                    </div>
                )}
            </ViewportPortal>
            {mode === "topology" && <Background color="#dfe5ec" gap={24} size={1} variant={BackgroundVariant.Dots} />}
            <Controls position="bottom-right" showInteractive={false} />
        </ReactFlow>
    );
}

export function TopologyCanvas() {
    const state = useTopologyStore();
    const task = mockTasks.find((item) => item.id === state.highlightedTaskId);
    const flow = useMemo(() => {
        const filtered = filterTopology(state.nodes, state.links, state.filters);
        return adaptTopology(filtered.nodes, filtered.links, {
            mode: state.viewMode,
            selectedLinkId: state.selectedLinkId,
            highlightedTaskNodeIds: state.layers.tasks
                ? [...(task?.assignedNodeIds ?? []), ...(task?.targetNodeIds ?? [])]
                : [],
            highlightedPathId: state.layers.tasks ? state.highlightedPathId : null,
            primaryLinkIds: mockPlanningResult.primarySubgraphLinkIds,
            backupLinkIds: mockPlanningResult.backupSubgraphLinkIds,
        });
    }, [state.nodes, state.links, state.filters, state.viewMode, state.selectedLinkId, state.highlightedPathId, state.layers.tasks, task]);
    const visibleNodes = state.layers.nodes ? flow.nodes : [];
    const visibleEdges = state.layers.links ? flow.edges : [];

    return (
        <div className={styles.canvas}>
            <TopologyScene
                incomingNodes={visibleNodes}
                incomingEdges={visibleEdges}
                mode={state.viewMode}
                viewRevision={state.viewRevision}
                centerRevision={state.centerRevision}
            />
            {!visibleNodes.length && (
                <div className={styles.emptyState}>
                    <strong>{state.nodes.length ? "当前筛选下无可见节点" : "当前场景暂无节点"}</strong>
                    {state.nodes.length > 0 && <button onClick={state.resetFilters}>清除筛选</button>}
                </div>
            )}
            <TopologyLegend />
        </div>
    );
}
