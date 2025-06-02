"""
Data models for OData metadata representation.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel

from .constants import ODATA_PRIMITIVE_TYPES, TYPE_MAP


class EntityProperty(BaseModel):
    name: str
    type: str  # OData type string (e.g., "Edm.String")
    nullable: bool = True
    is_key: bool = False
    description: Optional[str] = None

    def get_python_type(self) -> type:
        return ODATA_PRIMITIVE_TYPES.get(self.type, str)

    def get_python_type_hint(self) -> str:
        """Get the Python type hint string for this property."""
        py_type = self.get_python_type()
        type_str = TYPE_MAP.get(py_type, "str")  # Default to str if type not in map
        if self.nullable and not self.is_key:  # Keys are typically required even if nullable in OData model
            # Ensure Optional is handled correctly even if base type wasn't in TYPE_MAP
            optional_type_str = TYPE_MAP.get(Optional[py_type], f"Optional[{type_str}]")
            return optional_type_str
        return type_str


class EntityType(BaseModel):
    name: str
    properties: List[EntityProperty] = []
    key_properties: List[str] = []
    description: Optional[str] = None

    def get_key_properties(self) -> List[EntityProperty]:
        return [prop for prop in self.properties if prop.is_key]


class EntitySet(BaseModel):
    name: str
    entity_type: str
    creatable: bool = True
    updatable: bool = True
    deletable: bool = True
    searchable: bool = False
    description: Optional[str] = None


class FunctionImport(BaseModel):
    name: str
    http_method: str = "GET"
    return_type: Optional[str] = None
    parameters: List[EntityProperty] = []
    description: Optional[str] = None


class ODataMetadata(BaseModel):
    entity_types: Dict[str, EntityType] = {}
    entity_sets: Dict[str, EntitySet] = {}
    function_imports: Dict[str, FunctionImport] = {}
    service_url: str
    service_description: Optional[str] = None