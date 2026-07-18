import rawNetwork from "../../../../data/mock_uav_network.json";

import { adaptMockUavNodes } from "./uav-network-adapter";

export const mockNodes = adaptMockUavNodes(rawNetwork);
