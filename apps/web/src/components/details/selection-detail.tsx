"use client";

import { useTopologyStore } from "@/stores/use-topology-store";
import { LinkDetail } from "./link-detail";
import { NodeSummary } from "./node-summary";

export function SelectionDetail() {
    const selectedLinkId = useTopologyStore((state) => state.selectedLinkId);
    return selectedLinkId ? <LinkDetail /> : <NodeSummary />;
}
