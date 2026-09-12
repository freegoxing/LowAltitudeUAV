"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
    Control as LeafletControl,
    DomEvent,
    DomUtil,
    divIcon,
    type Marker as LeafletMarker,
    type PathOptions,
} from "leaflet";
import {
    Circle,
    MapContainer,
    Marker,
    Polygon,
    Polyline,
    ScaleControl,
    TileLayer,
    Tooltip,
    useMap,
    useMapEvents,
} from "react-leaflet";

import type { LayerVisibility, MapVisualPreference } from "@/types/dashboard";
import type { CommunicationLink, RescueNode, RescueNodeType } from "@/types/rescue";
import styles from "./rescue-map.module.css";
import { TopologyLegend } from "./topology-legend";

const YINGXIU_CENTER: [number, number] = [31.0607, 103.4858];
const YINGXIU_ZOOM = 13;

const markerSymbol: Record<RescueNodeType, string> = {
    command_center: "指",
    command_vehicle: "指",
    mission_drone: "巡",
    relay_drone: "继",
    communication_drone: "通",
    temporary_base_station: "基",
    satellite_terminal: "星",
    rescue_team: "救",
    medical_point: "医",
};

function markerIcon(
    node: RescueNode,
    selected: boolean,
    taskHighlighted: boolean,
    keyNode: boolean,
    taskRoleLabel: string | undefined,
    mode: RescueMapProps["mode"],
) {
    const classes = [
        styles.marker,
        styles[`marker${node.type}`],
        styles[`status${node.status}`],
        selected ? styles.selectedMarker : "",
        taskHighlighted ? styles.taskMarker : "",
        keyNode ? styles.keyMarker : "",
    ].filter(Boolean).join(" ");

    return divIcon({
        className: styles.markerContainer,
        html: mode === "hybrid"
            ? `<span class="${styles.hybridMarker}"><span class="${classes}">${markerSymbol[node.type]}</span><span class="${styles.hybridLabel}">${node.name}${taskRoleLabel ? ` · ${taskRoleLabel}` : ""}</span></span>`
            : `<span class="${classes}">${markerSymbol[node.type]}</span>`,
        iconSize: mode === "hybrid" ? [120, 34] : [30, 30],
        iconAnchor: mode === "hybrid" ? [15, 17] : [15, 15],
    });
}

function linkStyle(
    link: CommunicationLink,
    selected: boolean,
    primary: boolean,
    backup: boolean,
    dimmed: boolean,
): PathOptions {
    if (selected) return { color: "#1d4ed8", weight: 4, opacity: 1 };
    if (primary) return { color: "#ff3b73", weight: 4, opacity: 1 };
    if (backup) return { color: "#f59e0b", weight: 3, dashArray: "8 6", opacity: 1 };
    if (link.status === "interrupted") {
        return { color: "#dc2626", weight: 3, dashArray: "8 7", opacity: 0.9 };
    }
    if (link.status === "unstable") {
        return { color: "#d97706", weight: 3, dashArray: "6 6", opacity: 0.9 };
    }
    if (link.status === "degraded") {
        return { color: "#0284c7", weight: 3, dashArray: "10 6", opacity: 0.85 };
    }
    return dimmed
        ? { color: "#94a3b8", weight: 1.2, opacity: 0.22 }
        : { color: "#2563eb", weight: 3, opacity: 0.8 };
}

function ResetMapView({ centerRevision, viewRevision }: Pick<RescueMapProps, "centerRevision" | "viewRevision">) {
    const map = useMap();

    useEffect(() => {
        if (centerRevision > 0 || viewRevision > 0) {
            map.setView(YINGXIU_CENTER, YINGXIU_ZOOM, { animate: true });
        }
    }, [centerRevision, map, viewRevision]);

    return null;
}

function ClearSelection({ onClearSelection }: Pick<RescueMapProps, "onClearSelection">) {
    useMapEvents({ click: onClearSelection });
    return null;
}

function MapLegend() {
    const map = useMap();
    const [container, setContainer] = useState<HTMLDivElement | null>(null);

    useEffect(() => {
        const control = new LeafletControl({ position: "bottomleft" });
        control.onAdd = () => {
            const element = DomUtil.create("div");
            DomEvent.disableClickPropagation(element);
            setContainer(element);
            return element;
        };
        control.addTo(map);
        return () => {
            control.remove();
            setContainer(null);
        };
    }, [map]);

    return container ? createPortal(<TopologyLegend variant="map" />, container) : null;
}

export interface RescueMapProps {
    mode: "map" | "hybrid";
    nodes: RescueNode[];
    links: CommunicationLink[];
    selectedNodeId: string | null;
    selectedLinkId: string | null;
    highlightedTaskNodeIds: string[];
    highlightedPathId: string | null;
    keyNodeIds: string[];
    nodeRoleLabels: Record<string, string>;
    primaryLinkIds: string[];
    backupLinkIds: string[];
    layers: LayerVisibility;
    mapVisualPreference: MapVisualPreference;
    centerRevision: number;
    viewRevision: number;
    onSelectNode: (id: string) => void;
    onSelectLink: (id: string) => void;
    onMoveNode: (id: string, latitude: number, longitude: number) => void;
    onClearSelection: () => void;
}

export function RescueMap({
    mode,
    nodes,
    links,
    selectedNodeId,
    selectedLinkId,
    highlightedTaskNodeIds,
    highlightedPathId,
    keyNodeIds,
    nodeRoleLabels,
    primaryLinkIds,
    backupLinkIds,
    layers,
    mapVisualPreference,
    centerRevision,
    viewRevision,
    onSelectNode,
    onSelectLink,
    onMoveNode,
    onClearSelection,
}: RescueMapProps) {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const taskNodeIds = new Set(highlightedTaskNodeIds);
    const keyNodes = new Set(keyNodeIds);
    const primaryLinks = new Set(primaryLinkIds);
    const backupLinks = new Set(backupLinkIds);
    const hasPlannedSubgraph = primaryLinks.size > 0 || backupLinks.size > 0;
    const baseStation = nodes.find((node) => node.type === "temporary_base_station");

    return (
        <MapContainer
            center={YINGXIU_CENTER}
            className={`${styles.map} ${mapVisualPreference === "nodePriority" ? styles.nodePriority : styles.mapPriority}`}
            zoom={YINGXIU_ZOOM}
            minZoom={10}
            maxZoom={18}
            scrollWheelZoom
            wheelPxPerZoomLevel={160}
            zoomDelta={0.25}
            zoomSnap={0.25}
        >
            <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ScaleControl imperial={false} position="bottomright" />
            <MapLegend />
            <ResetMapView centerRevision={centerRevision} viewRevision={viewRevision} />
            <ClearSelection onClearSelection={onClearSelection} />

            {layers.risks && (
                <Polygon
                    pathOptions={{ color: "#dc2626", fillColor: "#fecaca", fillOpacity: 0.32, dashArray: "7 5" }}
                    positions={[
                        [31.074, 103.501],
                        [31.079, 103.516],
                        [31.068, 103.524],
                        [31.062, 103.508],
                    ]}
                >
                    <Tooltip permanent direction="center">滑坡风险区</Tooltip>
                </Polygon>
            )}

            {layers.coverage && (
                <Circle
                    center={baseStation ? [baseStation.latitude, baseStation.longitude] : YINGXIU_CENTER}
                    pathOptions={{ color: "#0284c7", fillColor: "#7dd3fc", fillOpacity: 0.16, dashArray: "8 6" }}
                    radius={2200}
                >
                    <Tooltip permanent direction="center">临时通信覆盖</Tooltip>
                </Circle>
            )}

            {layers.links && links.map((link) => {
                const source = nodesById.get(link.source);
                const target = nodesById.get(link.target);
                if (!source || !target) return null;

                return (
                    <Polyline
                        eventHandlers={{ click: () => onSelectLink(link.id) }}
                        key={link.id}
                        pathOptions={linkStyle(
                            link,
                            selectedLinkId === link.id || link.pathId === highlightedPathId,
                            primaryLinks.has(link.id),
                            backupLinks.has(link.id),
                            hasPlannedSubgraph,
                        )}
                        positions={[
                            [source.latitude, source.longitude],
                            [target.latitude, target.longitude],
                        ]}
                    >
                        <Tooltip sticky>{`${link.type} 链路 · ${link.status}`}</Tooltip>
                    </Polyline>
                );
            })}

            {layers.nodes && nodes.map((node) => (
                <Marker
                    draggable
                    eventHandlers={{
                        click: () => onSelectNode(node.id),
                        dragend: (event) => {
                            const location = (event.target as LeafletMarker).getLatLng();
                            onMoveNode(node.id, location.lat, location.lng);
                        },
                    }}
                    icon={markerIcon(
                        node,
                        selectedNodeId === node.id,
                        taskNodeIds.has(node.id),
                        keyNodes.has(node.id),
                        nodeRoleLabels[node.id],
                        mode,
                    )}
                    key={node.id}
                    position={[node.latitude, node.longitude]}
                >
                    <Tooltip direction="top" offset={[0, -13]}>{`${node.name} · ${nodeRoleLabels[node.id] ?? node.status}`}</Tooltip>
                </Marker>
            ))}
        </MapContainer>
    );
}
