# coding: utf-8

"""
    ETHZ Archiver Service

    REST API endpoint provider for presigned S3 upload and archiving workflow scheduling

    The version of the OpenAPI document: 0.1.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from __future__ import annotations
import pprint
import re  # noqa: F401
import json




from pydantic import BaseModel, ConfigDict, Field, StrictStr
from typing import Any, ClassVar, Dict, List
from openapi_server.models.complete_part import CompletePart
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

class CompleteUploadBody(BaseModel):
    """
    CompleteUploadBody
    """ # noqa: E501
    object_name: StrictStr = Field(alias="ObjectName")
    upload_id: StrictStr = Field(alias="UploadID")
    parts: List[CompletePart] = Field(alias="Parts")
    checksum_sha256: StrictStr = Field(alias="ChecksumSHA256")
    __properties: ClassVar[List[str]] = ["ObjectName", "UploadID", "Parts", "ChecksumSHA256"]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }


    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        # TODO: pydantic v2: use .model_dump_json(by_alias=True, exclude_unset=True) instead
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance of CompleteUploadBody from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias.

        This has the following differences from calling pydantic's
        `self.model_dump(by_alias=True)`:

        * `None` is only added to the output dict for nullable fields that
          were set at model initialization. Other fields with value `None`
          are ignored.
        """
        _dict = self.model_dump(
            by_alias=True,
            exclude={
            },
            exclude_none=True,
        )
        # override the default output from pydantic by calling `to_dict()` of each item in parts (list)
        _items = []
        if self.parts:
            for _item in self.parts:
                if _item:
                    _items.append(_item.to_dict())
            _dict['Parts'] = _items
        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of CompleteUploadBody from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "ObjectName": obj.get("ObjectName"),
            "UploadID": obj.get("UploadID"),
            "Parts": [CompletePart.from_dict(_item) for _item in obj.get("Parts")] if obj.get("Parts") is not None else None,
            "ChecksumSHA256": obj.get("ChecksumSHA256")
        })
        return _obj


