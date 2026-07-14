"""SkillOpt Gradient -- trajectory analysis and patch generation.

Analogous to gradient computation in neural network training: analyzes
minibatch rollout trajectories to produce skill-edit patches (the "gradient"
that drives skill updates).

Modules
-------
- reflect: minibatch trajectory analysis (gradient computation)
- aggregate: hierarchical patch merging (gradient aggregation)
"""

from uav_semantic_planner.skill_training.gradient.aggregate import (
    merge_patches,  # noqa: F401
)
from uav_semantic_planner.skill_training.gradient.reflect import (  # noqa: F401
    run_minibatch_reflect,
)
