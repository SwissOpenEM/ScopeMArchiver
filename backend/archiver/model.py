from pydantic import BaseModel


class ArchiveJob(BaseModel):
    filename: str


class Object(BaseModel):
    object_name: str
