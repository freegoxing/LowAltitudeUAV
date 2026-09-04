from uav_semantic_planner.utils.routing_planner import (
    MissionCandidateGroup,
    MissionCommunicationSpecification,
    MissionFlowSpec,
)
from uav_semantic_planner.utils.data_processing import candidate_group_features


def test_mcs_resolves_flow_receivers_from_tagged_candidate_groups():
    mission = MissionCommunicationSpecification(
        mission_id="SAR-1",
        mission_type="TASK-SAR",
        mission_priority=5,
        candidate_groups=[
            MissionCandidateGroup(
                group_id="medical",
                label="医疗组",
                node_ids=["GND-P-2", "UAV-M-4"],
            )
        ],
        mission_flows=[
            MissionFlowSpec(
                flow_id="F-medical",
                source="UAV-S-1",
                receivers=[],
                receiver_group_id="medical",
                purpose="医疗协同",
                priority=4,
                bandwidth_req="8 Mbps",
                latency_req="200 ms",
                reliability_req=0.97,
            )
        ],
    )

    assert mission.receivers_for(mission.mission_flows[0]) == ["GND-P-2", "UAV-M-4"]


def test_hgt_candidate_features_preserve_overlapping_group_membership():
    group_ids, features = candidate_group_features(
        {
            "mission_candidate_groups": [
                {"group_id": "search", "node_ids": ["UAV-R-1", "GND-P-1"]},
                {"group_id": "command", "node_ids": ["UAV-R-1", "GND-C-1"]},
            ]
        },
        {0: "UAV-R-1", 1: "GND-P-1", 2: "GND-C-1"},
    )

    assert group_ids == ["search", "command"]
    assert features.tolist() == [[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]]
