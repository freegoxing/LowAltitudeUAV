"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import dynamic from "next/dynamic";
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

import { mockMissionSubgraphs } from "@/data/mock-mission-subgraphs";
import { mockTasks } from "@/data/mock-tasks";
import { adaptTopology, nearestHandles } from "@/lib/topology-adapters";
import { filterTopology } from "@/lib/topology-filters";
import { topologyGroupBounds, topologyGroups } from "@/lib/topology-layout";
import { useTopologyStore } from "@/stores/use-topology-store";
import type { ViewMode } from "@/types/dashboard";
import type { CommunicationFlowEdge, RescueFlowNode } from "@/types/topology";
import { CommunicationEdge } from "./communication-edge";
import type { RescueMapProps } from "./rescue-map";
import { RescueNode } from "./rescue-node";
import { TopologyLegend } from "./topology-legend";
import styles from "./rescue-workspace.module.css";

const nodeTypes = { rescueNode: RescueNode };
const edgeTypes = { communicationLink: CommunicationEdge };
const fitOptions = { padding: 0.22, maxZoom: 1.35 };
const RescueMap = dynamic<RescueMapProps>(
    () => import("./rescue-map").then((module) => module.RescueMap),
    { ssr: false },
);

interface SceneProps {
    incomingNodes: RescueFlowNode[];
    incomingEdges: CommunicationFlowEdge[];
    mode: ViewMode;
    viewRevision: number;
    centerRevision: number;
}

function TopologyGroups() {
    return (
        <ViewportPortal>
            {topologyGroups.map((group) => {
                const bounds = topologyGroupBounds(group);
                return (
                    <div
                        className={styles.topologyGroup}
                        key={group.id}
                        style={{ height: bounds.height, left: bounds.x, top: bounds.y, width: bounds.width }}
                    >
                        <span>{group.label}</span>
                    </div>
                );
            })}
        </ViewportPortal>
    );
}

function TopologyScene({ incomingNodes, incomingEdges, mode, viewRevision, centerRevision }: SceneProps) {
    const state = useTopologyStore();
    const [nodes, setNodes, onNodesChange] = useNodesState(incomingNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(incomingEdges);
    const { fitView, getNodes } = useReactFlow();
    const previousMode = useRef(mode);
    const previousViewRevision = useRef(viewRevision);
    const updateEdgeHandles = useCallback(() => {
        const positionsById = new Map(
            getNodes().map((node) => [node.id, node.position]),
        );
        setEdges((currentEdges) => currentEdges.map((edge) => {
            const source = positionsById.get(edge.source);
            const target = positionsById.get(edge.target);
            return source && target
                ? { ...edge, ...nearestHandles(source, target) }
                : edge;
        }));
    }, [getNodes, setEdges]);

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
            onNodeDragStop={updateEdgeHandles}
            onEdgeClick={(_, edge) => state.selectLink(edge.id)}
            onPaneClick={state.clearSelection}
            proOptions={{ hideAttribution: true }}
            colorMode="light"
        >
            {mode === "topology" && <TopologyGroups />}
            {mode === "topology" && <Background color="#dfe5ec" gap={24} size={1} variant={BackgroundVariant.Dots} />}
            <Controls position="bottom-right" showInteractive={false} />
        </ReactFlow>
    );
}

export function TopologyCanvas() {
    const state = useTopologyStore();
    const task = mockTasks.find((item) => item.id === state.highlightedTaskId);
    const taskSubgraph = state.highlightedTaskId
        ? mockMissionSubgraphs[state.highlightedTaskId]
        : undefined;
    const filtered = useMemo(
        () => filterTopology(state.nodes, state.links, state.filters),
        [state.nodes, state.links, state.filters],
    );
    const highlightedTaskNodeIds = useMemo(
        () => state.layers.tasks
            ? [
                ...(task?.assignedNodeIds ?? []),
                ...(task?.targetNodeIds ?? []),
                ...(taskSubgraph?.primaryNodeIds ?? []),
                ...(taskSubgraph?.backupNodeIds ?? []),
            ]
            : [],
        [state.layers.tasks, task, taskSubgraph],
    );
    const flow = useMemo(() => {
        return adaptTopology(filtered.nodes, filtered.links, {
            mode: state.viewMode,
            selectedLinkId: state.selectedLinkId,
            highlightedTaskNodeIds,
            highlightedPathId: state.layers.tasks ? state.highlightedPathId : null,
            keyNodeIds: taskSubgraph?.keyNodeIds,
            primaryLinkIds: taskSubgraph?.primaryLinkIds ?? [],
            backupLinkIds: taskSubgraph?.backupLinkIds ?? [],
            mapVisualPreference: state.mapVisualPreference,
        });
    }, [filtered, highlightedTaskNodeIds, state.highlightedPathId, state.layers.tasks, state.mapVisualPreference, state.selectedLinkId, state.viewMode, taskSubgraph]);
    const visibleNodes = state.layers.nodes ? flow.nodes : [];
    const visibleEdges = state.layers.links ? flow.edges : [];

    return (
        <div className={styles.canvas}>
            {state.viewMode !== "topology" ? (
                <RescueMap
                    centerRevision={state.centerRevision}
                    highlightedPathId={state.layers.tasks ? state.highlightedPathId : null}
                    highlightedTaskNodeIds={highlightedTaskNodeIds}
                    keyNodeIds={taskSubgraph?.keyNodeIds ?? []}
                    layers={state.layers}
                    links={filtered.links}
                    mapVisualPreference={state.mapVisualPreference}
                    mode={state.viewMode}
                    nodes={filtered.nodes}
                    primaryLinkIds={taskSubgraph?.primaryLinkIds ?? []}
                    backupLinkIds={taskSubgraph?.backupLinkIds ?? []}
                    onClearSelection={state.clearSelection}
                    onMoveNode={state.updateNodeLocation}
                    onSelectLink={state.selectLink}
                    onSelectNode={state.selectNode}
                    selectedLinkId={state.selectedLinkId}
                    selectedNodeId={state.selectedNodeId}
                    viewRevision={state.viewRevision}
                />
            ) : (
                <TopologyScene
                    centerRevision={state.centerRevision}
                    incomingEdges={visibleEdges}
                    incomingNodes={visibleNodes}
                    mode={state.viewMode}
                    viewRevision={state.viewRevision}
                />
            )}
            {!(state.viewMode !== "topology" ? filtered.nodes.length : visibleNodes.length) && (
                <div className={styles.emptyState}>
                    <strong>{state.nodes.length ? "当前筛选下无可见节点" : "当前场景暂无节点"}</strong>
                    {state.nodes.length > 0 && <button onClick={state.resetFilters}>清除筛选</button>}
                </div>
            )}
            {state.viewMode === "topology" && <TopologyLegend />}
        </div>
    );
}
