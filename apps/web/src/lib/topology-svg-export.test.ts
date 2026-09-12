import assert from "node:assert/strict";
import test from "node:test";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import { adaptTopology } from "@/lib/topology-adapters";
import { createTopologySvg } from "@/lib/topology-svg-export";

test("creates a 3:1 complete SVG with export-specific positions", () => {
    const flow = adaptTopology(mockNodes, mockLinks, {
        mode: "topology",
        selectedLinkId: null,
        highlightedTaskNodeIds: [],
        highlightedPathId: null,
        primaryLinkIds: [],
        backupLinkIds: [],
        mapVisualPreference: "nodePriority",
    });

    const svg = createTopologySvg(flow.nodes, flow.edges);

    assert.match(svg, /<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/);
    assert.match(svg, /viewBox="0 0 1500 500"/);
    assert.match(svg, /<rect[^>]+class="topology-node"/);
    assert.match(svg, /<path[^>]+class="topology-link"/);
    assert.match(svg, /<path[^>]+d="M [^"]+ C [^"]+"/);
    assert.match(svg, />指挥调度</);
    assert.match(svg, /<rect x="760" y="255" width="720" height="215"/);
});
