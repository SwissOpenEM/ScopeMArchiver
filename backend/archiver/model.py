from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Job(BaseModel):
    id: str
    type: str
    jobResultObject: Optional[object] = None
    jobStatusMessage: Optional[str] = None


class DataFile(BaseModel):
    # Relative path of the file within the dataset folder ,
    path: str
    #  Uncompressed file size in bytes ,
    size: Optional[int] = None
    # Time of file creation on disk, format according to chapter 5.6 internet date/time format in RFC 3339. Local times without
    # timezone/offset info are automatically transformed to UTC using the timezone of the API server ,
    time: Optional[datetime] = None
    # Checksum for the file, e.g. its sha-2 hashstring ,
    chk: Optional[str] = None
    # optional: user ID name as seen on filesystem ,
    uid: Optional[str] = None
    # optional: group ID name as seen on filesystem ,
    gid: Optional[str] = None
    # optional: Posix permission bits ,
    perm: Optional[str] = None
    # Functional or user account name who created this instance ,
    createdBy: Optional[str] = None
    # Functional or user account name who last updated this instance ,
    updatedBy: Optional[str] = None
    # createdAt (string, optional),
    createdAt: Optional[datetime] = None
    # updatedAt (string, optional)
    updatedAt: Optional[datetime] = None


class OrigDataBlock(BaseModel):
    # id (string),
    id: str
    # Total size in bytes of all files contained in the dataFileList ,
    size: int
    # Defines the group which owns the data, and therefore has unrestricted access to this data. Usually a pgroup like p12151 ,
    ownerGroup: str

    # Optional additional groups which have read access to the data. Users which are member in one of the groups listed here are allowed to
    # access this data. The special group 'public' makes data available to all users ,
    accessGroups: Optional[List[str]] = None

    # Optional additional groups which have read and write access to the data. Users which are member in one of the groups listed here are
    # allowed to access this data. ,
    instrumentGroup: Optional[str] = None
    # Functional or user account name who created this instance ,
    createdBy: Optional[str] = None

    # Functional or user account name who last updated this instance ,
    updatedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    datasetId: Optional[str] = None
    dataFileList: Optional[List[DataFile]] = None
    rawdatasetId: Optional[str] = None
    derivedDatasetId: Optional[str] = None


class DataBlock(BaseModel):
    # id (string),
    id: str
    # Unique identifier given bey archive system to the stored datablock. This id is used when data is retrieved back. ,
    archiveId: str
    # Total size in bytes of all files in datablock when unpacked
    size: int
    # Size of datablock package file
    packedSize: Optional[int] = None
    # Algoritm used for calculation of checksums, e.g. sha2
    chkAlg: Optional[str] = None
    # Version string defining format of how data is packed and stored in archive
    version: str
    # Defines the group which owns the data, and therefore has unrestricted access to this data. Usually a pgroup like p12151 ,
    ownerGroup: str
    # Optional additional groups which have read access to the data. Users which are member in one of the groups listed here are allowed to
    # access this data. The special group 'public' makes data available to all users ,
    accessGroups: Optional[List[str]] = None
    # Optional additional groups which have read and write access to the data. Users which are member in one of the groups listed here are
    # allowed to access this data. ,
    instrumentGroup: Optional[str] = None
    # Functional or user account name who created this instance ,
    createdBy: Optional[str] = None
    # Functional or user account name who last updated this instance ,
    updatedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    datasetId: Optional[str] = None
    dataFileList: Optional[List[DataFile]] = None
    rawDatasetId: Optional[str] = None
    derivedDatasetId: Optional[str] = None


class DatasetLifecycle(BaseModel):
    id: Optional[str] = None

    # Flag which is true, if dataset is available to be archived and no archive job for this dataset exists yet. ,
    archivable: Optional[bool] = None

    # Flag which is true, if dataset is stored on archive system and is ready to be retrieved. ,
    retrievable: Optional[bool] = None

    # Flag which is true, if dataset can be published. Usually requires a longterm storage option on tape or similar. ,
    publishable: Optional[bool] = None

    # Day when dataset will be removed from disk, assuming that is already stored on tape. ,
    dateOfDiskPurging: Optional[str] = None

    # Day when the dataset's future fate will be evaluated again, e.g. to decide if the dataset can be deleted from archive. ,
    archiveRetentionTime: Optional[str] = None

    # Day when dataset is supposed to become public according to data policy ,
    dateOfPublishing: Optional[str] = None

    # Day when dataset was published. ,
    publishedOn: Optional[str] = None

    # Flag which is true, if full dataset is available on central fileserver. If false data needs to be copied from decentral storage place
    # to a cache server before the ingest. This information needs to be transferred to the archive system at archive time ,
    isOnCentralDisk: Optional[bool] = None

    # Short string defining current status of Dataset with respect to storage on disk/tape. ,
    archiveStatusMessage: Optional[str] = None

    # Latest message for this dataset concerning retrieve from archive system. ,
    retrieveStatusMessage: Optional[str] = None

    # Detailed status or error message returned by archive system when archiving this dataset. ,
    archiveReturnMessage: Optional[object] = None

    # Detailed status or error message returned by archive system when retrieving this dataset. ,
    retrieveReturnMessage: Optional[object] = None

    # Location of the last export destination. ,
    exportedTo: Optional[str] = None

    # Set to true when checksum tests after retrieve of datasets were successful ,
    retrieveIntegrityCheck: Optional[bool] = None


class ArchiveJob(BaseModel):
    origDataBlocks: List[DataFile]


class RetrievalJob(BaseModel):
    filename: str


class Dataset(BaseModel):
    id: Optional[str] = None
    datasetlifecycle: DatasetLifecycle


class StorageObject(BaseModel):
    object_name: str
