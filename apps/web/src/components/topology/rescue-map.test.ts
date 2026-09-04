import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const packageManifest = readFileSync(
    new URL("../../../package.json", import.meta.url),
    "utf8",
);

test("declares the packages required for the interactive rescue map", () => {
    assert.match(packageManifest, /"leaflet"\s*:/);
    assert.match(packageManifest, /"react-leaflet"\s*:/);
    assert.match(packageManifest, /"@types\/leaflet"\s*:/);
});

const mapSource = readFileSync(
    new URL("./rescue-map.tsx", import.meta.url),
    "utf8",
);

test("uses OSM tiles with visible attribution and an Yingxiu initial view", () => {
    assert.match(mapSource, /tile\.openstreetmap\.org\/\{z\}\/\{x\}\/\{y\}\.png/);
    assert.match(mapSource, /OpenStreetMap/);
    assert.match(mapSource, /31\.0607/);
    assert.match(mapSource, /103\.4858/);
    assert.match(mapSource, /ScaleControl/);
});
