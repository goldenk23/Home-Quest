from typing import TypedDict, List, Optional

class MetadataDict(TypedDict):
    project_name: str
    description: str
    created: str
    modified: str
    unit: str
    grid_spacing: int
    canvas_width: int
    canvas_height: int
    zoom_level: float

class RoomDict(TypedDict):
    id: str
    name: str
    x: float
    y: float
    width: float
    height: float
    fill_color: str
    outline_color: str
    group_tag: str
    flooring: dict 

class FurnitureDict(TypedDict):
    id: str
    image_path: str
    x: float
    y: float
    image_filename: str  # Add filename
    image_name: str     # Add base name
    scale: float
    angle: float

class ShapeDict(TypedDict):
    id: str
    type: str
    points: List[List[float]]
    outline_color: str
    fill_color: str
    width: int
    style: Optional[str]

class TextDict(TypedDict):
    id: str
    content: str
    x: float
    y: float
    font: str
    color: str

class LayoutDict(TypedDict):
    version: str
    metadata: MetadataDict
    rooms: List[RoomDict]
