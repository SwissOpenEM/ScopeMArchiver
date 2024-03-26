from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Job(BaseModel):
    id: str
    type: str
    jobResultObject: Optional[object] = None
    jobStatusMessage: Optional[str]


class DataFile(BaseModel):
    # Relative path of the file within the dataset folder ,
    path: str
    #  Uncompressed file size in bytes ,
    size: Optional[int]
    # Time of file creation on disk, format according to chapter 5.6 internet date/time format in RFC 3339. Local times without timezone/offset info are automatically transformed to UTC using the timezone of the API server ,
    time: Optional[datetime]
    # Checksum for the file, e.g. its sha-2 hashstring ,
    chk: Optional[str]
    # optional: user ID name as seen on filesystem ,
    uid: Optional[str]
    # optional: group ID name as seen on filesystem ,
    gid: Optional[str]
    # optional: Posix permission bits ,
    perm: Optional[str]
    # Functional or user account name who created this instance ,
    createdBy: Optional[str]
    # Functional or user account name who last updated this instance ,
    updatedBy: Optional[str]
    # createdAt (string, optional),
    createdAt: Optional[datetime]
    # updatedAt (string, optional)
    updatedAt: Optional[datetime]


class OrigDataBlock(BaseModel):
    # id (string),
    id: str
# Total size in bytes of all files contained in the dataFileList ,
    size: int
# Defines the group which owns the data, and therefore has unrestricted access to this data. Usually a pgroup like p12151 ,
    ownerGroup: str

    # Optional additional groups which have read access to the data. Users which are member in one of the groups listed here are allowed to access this data. The special group 'public' makes data available to all users ,
    accessGroups: Optional[List[str]]

    # Optional additional groups which have read and write access to the data. Users which are member in one of the groups listed here are allowed to access this data. ,
    instrumentGroup: Optional[str]
    # Functional or user account name who created this instance ,
    createdBy: Optional[str]

    # Functional or user account name who last updated this instance ,
    updatedBy: Optional[str]
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]
    datasetId: Optional[str]
    dataFileList: Optional[List[DataFile]]
    rawdatasetId: Optional[str]
    derivedDatasetId: Optional[str]


class DataBlock(BaseModel):
    # id (string),
    id: str
    # Unique identifier given bey archive system to the stored datablock. This id is used when data is retrieved back. ,
    archiveId: str
    # Total size in bytes of all files in datablock when unpacked
    size: int
    # Size of datablock package file
    packedSize: Optional[int]
    # Algoritm used for calculation of checksums, e.g. sha2
    chkAlg: Optional[str]
    # Version string defining format of how data is packed and stored in archive
    version: str
    # Defines the group which owns the data, and therefore has unrestricted access to this data. Usually a pgroup like p12151 ,
    ownerGroup: str
    # Optional additional groups which have read access to the data. Users which are member in one of the groups listed here are allowed to access this data. The special group 'public' makes data available to all users ,
    accessGroups: Optional[List[str]]
    # Optional additional groups which have read and write access to the data. Users which are member in one of the groups listed here are allowed to access this data. ,
    instrumentGroup: Optional[str]
    # Functional or user account name who created this instance ,
    createdBy: Optional[str]
    # Functional or user account name who last updated this instance ,
    updatedBy: Optional[str]
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]
    datasetId: Optional[str]
    dataFileList: Optional[List[DataFile]]
    rawDatasetId: Optional[str]
    derivedDatasetId: Optional[str]


class ArchiveJob(BaseModel):
    origDataBlocks: List[DataFile]


class RetrievalJob(BaseModel):
    filename: str


class Dataset(BaseModel):
    id: str


class StorageObject(BaseModel):
    object_name: str
