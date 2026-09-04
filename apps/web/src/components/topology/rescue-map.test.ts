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
