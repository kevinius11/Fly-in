from dataclasses import dataclass
from enum import Enum


class ZoneType(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass(frozen=True)
class Zone:
    name: str
    x: int
    y: int
    zone_type: ZoneType
    max_drones: int
    color: str | None = None
    is_start: bool = False
    is_end: bool = False


@dataclass(frozen=True)
class Connection:
    zone_a: str
    zone_b: str
    max_link_capacity: int


@dataclass(frozen=True)
class MapData:
    nb_drones: int
    zones: dict[str, Zone]
    connections: list[Connection]
    start_hub: Zone
    end_hub: Zone
