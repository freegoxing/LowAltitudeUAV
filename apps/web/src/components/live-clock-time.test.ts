import assert from "node:assert/strict";
import test from "node:test";

import { formatClockTime } from "./layout/live-clock-time";

test("formats a date as a zero-padded 24-hour clock time", () => {
    const date = new Date(2026, 6, 16, 9, 5, 7);

    assert.equal(formatClockTime(date), "09:05:07");
});
