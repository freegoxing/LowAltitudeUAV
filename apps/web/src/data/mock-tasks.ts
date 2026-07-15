import type { RescueTask } from "@/types/rescue";
export const mockTasks: RescueTask[] = [
    { id: "t-1", name: "东岭失联人员搜救", type: "人员搜救", priority: "P0", status: "running", progress: 68, assignedNodeIds: ["n-team", "n-relay"], targetNodeIds: [], region: "东岭搜救区", startedAt: "08:42" },
    { id: "t-2", name: "河谷临时通信覆盖", type: "通信中继", priority: "P1", status: "planning", progress: 32, assignedNodeIds: ["n-base"], targetNodeIds: [], region: "河谷安置区", startedAt: "09:06" },
    { id: "t-3", name: "医疗物资定点投送", type: "物资投送", priority: "P1", status: "pending", progress: 0, assignedNodeIds: [], targetNodeIds: [], region: "西坡医疗点" },
    { id: "t-4", name: "北坡滑坡灾情侦察", type: "灾情侦察", priority: "P2", status: "completed", progress: 100, assignedNodeIds: [], targetNodeIds: [], region: "北坡风险区", startedAt: "07:50" },
];
