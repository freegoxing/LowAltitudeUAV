import { create } from "zustand";
import type { ConnectionStatus } from "@/types/dashboard";
interface ConnectionState { apiStatus: ConnectionStatus; websocketStatus: ConnectionStatus; setApiStatus: (status: ConnectionStatus) => void; setWebsocketStatus: (status: ConnectionStatus) => void; }
export const useConnectionStore = create<ConnectionState>((set) => ({ apiStatus: "connected", websocketStatus: "connected", setApiStatus: (apiStatus) => set({ apiStatus }), setWebsocketStatus: (websocketStatus) => set({ websocketStatus }) }));
