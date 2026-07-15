import { Crosshair, Filter, Focus, RotateCcw } from "lucide-react";

import { useTopologyStore } from "@/stores/use-topology-store";
import type { ViewMode } from "@/types/dashboard";
import type { LinkStatus, LinkType, NodeStatus, RescueNodeType } from "@/types/rescue";
import styles from "./rescue-workspace.module.css";

const modes: [ViewMode, string][] = [["map", "地图"], ["topology", "拓扑"], ["hybrid", "混合"]];
const layers = [["nodes", "节点"], ["links", "链路"], ["tasks", "任务"], ["risks", "风险区"], ["coverage", "覆盖"]] as const;
const nodeTypeText: Record<RescueNodeType, string> = {
    command_center: "指挥中心",
    command_vehicle: "指挥车",
    mission_drone: "任务无人机",
    relay_drone: "中继无人机",
    communication_drone: "通信无人机",
    temporary_base_station: "临时基站",
    satellite_terminal: "卫星终端",
    rescue_team: "救援队",
    medical_point: "医疗点",
    shelter: "安置点",
    trapped_area: "被困区域",
};
const nodeStatusText: Record<NodeStatus, string> = { online: "在线", busy: "忙碌", warning: "告警", offline: "离线" };
const linkTypeText: Record<LinkType, string> = { primary: "主链路", relay: "中继", backup: "备用", emergency: "应急" };
const linkStatusText: Record<LinkStatus, string> = { normal: "正常", degraded: "弱化", unstable: "不稳定", interrupted: "中断" };

function toggleValue<T extends string>(values: T[], value: T) {
    return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function TopologyToolbar() {
    const state = useTopologyStore();
    return (
        <header className={styles.toolbar}>
            <div className={styles.toolbarTitle}><strong>态势工作区</strong><span>{state.nodes.length} 节点 · {state.links.length} 链路</span></div>
            <div className={styles.modes} role="group" aria-label="视图模式">{modes.map(([key, label]) => <button aria-pressed={state.viewMode === key} className={state.viewMode === key ? styles.active : ""} key={key} onClick={() => state.setViewMode(key)}>{label}</button>)}</div>
            <details className={styles.filterMenu}>
                <summary><Filter size={13} />图层与筛选</summary>
                <div className={styles.filterPanel}>
                    <fieldset><legend>图层</legend>{layers.map(([key, label]) => <label key={key}><input type="checkbox" checked={state.layers[key]} onChange={() => state.toggleLayer(key)} />{label}</label>)}</fieldset>
                    <fieldset><legend>节点类型</legend>{(Object.keys(nodeTypeText) as RescueNodeType[]).map((value) => <label key={value}><input type="checkbox" checked={state.filters.nodeTypes.includes(value)} onChange={() => state.setNodeTypes(toggleValue(state.filters.nodeTypes, value))} />{nodeTypeText[value]}</label>)}</fieldset>
                    <fieldset><legend>节点状态</legend>{(Object.keys(nodeStatusText) as NodeStatus[]).map((value) => <label key={value}><input type="checkbox" checked={state.filters.nodeStatuses.includes(value)} onChange={() => state.setNodeStatuses(toggleValue(state.filters.nodeStatuses, value))} />{nodeStatusText[value]}</label>)}</fieldset>
                    <fieldset><legend>链路类型</legend>{(Object.keys(linkTypeText) as LinkType[]).map((value) => <label key={value}><input type="checkbox" checked={state.filters.linkTypes.includes(value)} onChange={() => state.setLinkTypes(toggleValue(state.filters.linkTypes, value))} />{linkTypeText[value]}</label>)}</fieldset>
                    <fieldset><legend>链路状态</legend>{(Object.keys(linkStatusText) as LinkStatus[]).map((value) => <label key={value}><input type="checkbox" checked={state.filters.linkStatuses.includes(value)} onChange={() => state.setLinkStatuses(toggleValue(state.filters.linkStatuses, value))} />{linkStatusText[value]}</label>)}</fieldset>
                    <button className={styles.clearFilters} onClick={state.resetFilters}>清除筛选</button>
                </div>
            </details>
            <div className={styles.actions}>
                <button aria-label="自动布局" title="自动布局" onClick={() => { state.setViewMode("topology"); state.resetView(); }}><Focus size={14} /></button>
                <button aria-label="居中视图" title="居中视图" onClick={state.centerView}><Crosshair size={14} /></button>
                <button aria-label="重置视图" title="重置视图" onClick={state.resetView}><RotateCcw size={14} /></button>
            </div>
        </header>
    );
}
