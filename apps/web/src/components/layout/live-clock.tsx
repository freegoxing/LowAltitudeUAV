"use client";

import { useEffect, useState } from "react";

import { formatClockTime } from "./live-clock-time";
import styles from "./workspace-layout.module.css";

export function LiveClock() {
    const [time, setTime] = useState("--:--:--");

    useEffect(() => {
        const updateTime = () => setTime(formatClockTime(new Date()));

        updateTime();
        const intervalId = window.setInterval(updateTime, 1000);

        return () => window.clearInterval(intervalId);
    }, []);

    return <time className={styles.time}>{time}</time>;
}
