import type { RescueAlert } from "@/types/rescue";
export const mockAlerts: RescueAlert[] = [
    { id: "a-1", level: "critical", title: "临时基站负载过高", description: "B-02 当前负载已达 84%", relatedObject: "临时基站 B-02", status: "processing", occurredAt: "09:28" },
    { id: "a-2", level: "high", title: "备用链路波动", description: "连续三个采样周期出现丢包", relatedObject: "链路 L-03", status: "open", occurredAt: "09:21" },
    { id: "a-3", level: "medium", title: "无人机电量提醒", description: "R-03 剩余电量 68%", relatedObject: "中继无人机 R-03", status: "open", occurredAt: "09:12" },
];
