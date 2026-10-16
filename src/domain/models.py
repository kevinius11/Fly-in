"""Immutable data models for maps, zones, and physical connections."""

from dataclasses import dataclass
from enum import Enum


class ZoneType(Enum):
    """Classify zones by their movement and access behavior."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass(frozen=True)
class Zone:
    """Store a zone's identity, coordinates, type, capacity, and markers.

    Attributes:
        name: Unique zone name used by connections and routes.
        x: Horizontal map coordinate.
        y: Vertical map coordinate.
        zone_type: Movement and access classification.
        max_drones: Maximum ordinary occupancy for this zone.
        color: Optional display color from map metadata.
        is_start: Whether this zone is the map origin.
        is_end: Whether this zone is the delivery destination.
    """

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
    """Describe a physical link and its simultaneous-use capacity.

    Attributes:
        zone_a: Name of one endpoint.
        zone_b: Name of the other endpoint.
        max_link_capacity: Maximum drones that may use the link at once.
    """

    zone_a: str
    zone_b: str
    max_link_capacity: int


@dataclass(frozen=True)
class MapData:
    """Collect validated static data parsed from one map file.

    Attributes:
        nb_drones: Number of drones to create for the simulation.
        zones: Zones indexed by their unique names.
        connections: Physical links between zones.
        start_hub: Origin zone for all routes.
        end_hub: Destination zone for all routes.
    """

    nb_drones: int
    zones: dict[str, Zone]
    connections: list[Connection]
    start_hub: Zone
    end_hub: Zone
