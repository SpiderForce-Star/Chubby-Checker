from dataclasses import dataclass
from typing import Optional

@dataclass
class Piece:
    mark: str
    description: str
    quantity: int
    length: Optional[str] = None
    length_inches: Optional[float] = None
    weight: Optional[float] = None
    section: Optional[str] = None
    category: Optional[str] = None
    source: str = "shipper"
