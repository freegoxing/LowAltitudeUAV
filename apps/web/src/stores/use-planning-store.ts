import { create } from "zustand";
import { mockPlanningResult } from "@/data/mock-planning-result";
import { mockTasks } from "@/data/mock-tasks";
import type { SimulationStatus } from "@/types/dashboard";
interface PlanningState { tasks: typeof mockTasks; result: typeof mockPlanningResult; simulationStatus: SimulationStatus; setSimulationStatus: (status: SimulationStatus) => void; }
export const usePlanningStore = create<PlanningState>((set) => ({ tasks: mockTasks, result: mockPlanningResult, simulationStatus: "idle", setSimulationStatus: (simulationStatus) => set({ simulationStatus }) }));
