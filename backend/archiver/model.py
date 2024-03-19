from pydantic import BaseModel


class ArchiveJob(BaseModel):
    filename: str


class RetrievalJob(BaseModel):
    filename: str


class Dataset(BaseModel):
    id: str


class StorageObject(BaseModel):
    object_name: str
