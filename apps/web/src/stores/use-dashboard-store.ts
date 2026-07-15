import { create } from "zustand";
import type { ConsoleTab } from "@/types/dashboard";
interface DashboardState { consoleTab: ConsoleTab; selectedTaskId: string | null; setConsoleTab: (tab: ConsoleTab) => void; selectTask: (id: string) => void; }
export const useDashboardStore = create<DashboardState>((set) => ({ consoleTab: "events", selectedTaskId: "t-1", setConsoleTab: (consoleTab) => set({ consoleTab }), selectTask: (selectedTaskId) => set({ selectedTaskId }) }));
