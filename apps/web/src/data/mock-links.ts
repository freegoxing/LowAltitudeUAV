import rawNetwork from "../../../../data/mock_uav_network.json";

import { adaptMockUavLinks } from "./uav-network-adapter";

export const mockLinks = adaptMockUavLinks(rawNetwork);
