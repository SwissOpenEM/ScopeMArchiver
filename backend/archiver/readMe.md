# Archiving Flow

### Upload Data Sequence

```mermaid
sequenceDiagram
  autonumber
  participant C as Client 
  participant L as Landing Zone
  participant LTS
  participant A as Archival Service
  participant S as SciCat 

  C->>S: Register DataSets <br> POST api/v3/Datasets
  activate S
  S-->>C: PID
  deactivate S
  C-)S: Create OrigDataBlocks <br> POST api/v3/OrigDatablocks
  C->>+A: PID
  A-->>-C: Presigned Upload URL
  C->>L: Upload dataset
  C -) S: Task: {"datasetlifecycle": {"archivable":"True" , <br> "archiveStatusMessage": "isOnCentralDisk"}} <br> PATCH /api/v3/Datasets/{DatasetId}

```

  <!-- A-)J: Create Datablocks Task
  activate J
  L->>AS: Task: Create Datablocks
  loop Retry: Exponential backoff
    J->>S: Register Datablocks POST /api/v4/Datasets/{DatasetID}
  end
  deactivate J
  loop Retry: Exponential backoff
    S->>A: Request Archival POST /api/v1/archive
  end
  A->>J: Create Archive Task
  activate J
  AS ->>LTS: Task: Archive
  loop Retry: Exponential backoff
    J ->> S: Update Job status PUT /api/v3/Jobs/{JobId} 
  end
  deactivate J -->

### [Archival Task Chain](./archival_tasks.py)

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant L as Landing Zone
  participant J as Worker
  participant A as Staging
  participant S as SciCat
  participant LTS as LTS

  S --) AS: Archive: {"datasetid":"id", <br> "origDataBlocks" : [dataFile], "jobId", "id"}<br> POST /api/v1/archive/job
  
   AS --) J: Create Archiving Pipeline
  loop Retry: Exponential backoff
    activate J
      J --) S: {"jobStatusMessage": "inProgress"}   <br> PATCH /api/v3/Jobs/{JobId}
    deactivate J
  end
  loop Retry: Exponential backoff
    activate J
      J --) S: {"datasetlifecycle": {"archiveStatusMessage": "started"}}   <br> PATCH /api/v3/Dataset/{DatasetId}
    deactivate J
  end
  critical 
    activate J
    J -->> L:  Create Datablocks
    deactivate J
  option Failure (Disk space, ...)
    activate J
    J -->> L: Cleanup, restore files
    J -->> S: Report Error
    deactivate J
  end
  critical
    activate J
    L -->> A: Move to Staging
    deactivate J
  option Failure (Disk space, ...)
    activate J
    J -->> J: Cleanup Staging
    J -->> S: Report Error
    deactivate J
  end
  loop Retry: Exponential backoff
    activate J
    J -->> S: Task: Register datablocks <br> POST /api/v4/Datasets/{DatasetID}
    deactivate J
  end
  
  critical
    activate J
    A -->> LTS: Move Datablocks to LTS
    deactivate J
  option Failure
    activate J
    J -->> LTS: Cleanup
    J -->> S: Report Error
    deactivate J
  end
  critical 
    activate J
    J -->> LTS:  Validate Datablocks in LTS
    deactivate J
  option Validation Failure
    activate J
    A -->> LTS: Retry once: Move datablocks to LTS
    J -->> S: Report Error
    deactivate J
  end
  loop Retry: Exponential backoff
    activate J
    J -->> S: {"datasetlifecycle": {"retrievable": True, <br> "archiveStatusMessage": "datasetOnArchiveDisk"}} <br> PATCH /api/v3/Datasets/{DatasetId}
    deactivate J
  end 
  loop Retry: Exponential backoff
    activate J
    J -->> S: {"jobStatusMessage": "finishedSuccessful"} <br>PATCH /api/v3/Jobs/{JobId}
    deactivate J
  end 
```


### Retrieval Task Chain

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant J as Worker
  participant R as Staging
  participant S as SciCat
  participant LTS as LTS

  AS --) J: Create Retrieval Task JobID, DatasetID
  loop Retry: Exponential backoff
    activate J
      J -->> S: {"jobStatusMessage": "inProgress"}   <br> PATCH /api/v3/Jobs/{JobId}
      J -->> S: {"datasetlifecycle": {"retrieveStatusMessage": "started"}}   <br> PATCH /api/v3/Datasets/{DatasetId}
    deactivate J
  end
  critical
    activate J
    LTS -->> R: Task: Download Datablocks from LTS
    deactivate J
  option Retrieval Failure
    activate J
    J -->> S: Report Error
    J -->> R: Cleanup Files
    deactivate J
  end
  critical
    activate J
    J -->> R: Task: Validate Datablocks
    deactivate J
  end
  loop Retry: Exponential backoff
    activate J
    J -->> S: {"jobStatusMessage": "finishedSuccessful"}   <br> PATCH /api/v3/Jobs/{JobId}
    J -->> S: {"datasetlifecycle":<br> {"retrieveStatusMessage": "datasetRetrieved"}}<br> PATCH /api/v3/Datasets/{DatasetId}
    J -->> S: POST Retrieval URL <endpoint>
    deactivate J
  end 

```
