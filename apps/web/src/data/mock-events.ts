import type { SystemEvent } from "@/types/rescue";
export const mockEvents: SystemEvent[] = [
    { id: "e-1", time: "09:32:18", type: "network", message: "主通信子图连通率恢复至 100%", relatedObject: "Plan-07", priority: "low", status: "completed" },
    { id: "e-2", time: "09:28:06", type: "alert", message: "临时基站负载超过预警阈值", relatedObject: "B-02", priority: "high", status: "active" },
    { id: "e-3", time: "09:17:42", type: "task", message: "东岭搜救任务完成区域扫描", relatedObject: "任务 T-01", priority: "medium", status: "active" },
];
