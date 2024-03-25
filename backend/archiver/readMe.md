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
  C--)S: Create OrigDataBlocks <br> POST api/v3/OrigDatablocks
  C->>+A: PID
  A-->>-C: Presigned Upload URL
  C->>L: Upload dataset
  C->>A: Upload finished <br> GET /api/v1/upload

```

  <!-- A-)J: Create Datablocks Task
  activate J
  L->>AS: Task: Create Datablocks
  loop Retry
    J->>S: Register Datablocks POST /api/v4/Datasets/{DatasetID}
  end
  deactivate J
  loop Retry
    S->>A: Request Archival POST /api/v1/archive
  end
  A->>J: Create Archive Task
  activate J
  AS ->>LTS: Task: Archive
  loop Retry
    J ->> S: Update Job status PUT /api/v3/Jobs/{JobId} 
  end
  deactivate J -->

### Post-Upload Task Chain

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant AS as Archival Service
  participant J as Worker
  participant L as Landing Zone
  participant S as SciCat
  participant A as Archiveable Storage

  C -->> AS: Upload finished <br> GET /api/v1/upload
  AS --) J: Create DataBlocks Task
  activate J
  L -->> L: Task: Create Datablocks
  deactivate J
  critical
    activate J
    L -->> A: Task: Upload to Archivable Storage
    deactivate J
  end
  loop Retry
    activate J
    J -->> S: Task: Register datablocks <br> POST /api/v4/Datasets/{DatasetID}
    deactivate J
  end
  loop Retry
    activate J
    J -->> S: Task: Update Dataset Lifecycle <br> PUT /api/v3/Datasets/{DatasetId}
    deactivate J
  end
```

### Archival Task Chain

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant J as Worker
  participant A as Archiveable Storage
  participant S as SciCat
  participant LTS as LTS

  S --) AS: Archive: GET /api/v1/archive/datasets/{DatasetId}
  AS --) J: Create Archival Task
  loop Retry - Does scicat do this?
      AS --) S: {"jobStatusMessage": "jobForwarded"}   <br> PUT /api/v3//{JobId}
  end
  loop Retry
    activate J
      J --) S: {"jobStatusMessage": "inProgress"}   <br> PUT /api/v3/Jobs/{JobId}
      J --) S: {"datasetlifecycle": {"archiveStatusMessage": "started"}}   <br> PUT /api/v3/Dataset/{DatasetId}
    deactivate J
  end
  critical
    activate J
    A -->> LTS: Task: Move Datablocks to LTS
    deactivate J
  end
  critical 
    activate J
    J -->> LTS: Task: Validate Datablocks in LTS
    deactivate J
  end
  loop Retry
    activate J
    J -->> S: {"datasetlifecycle": {"retrievable": True, <br> "archiveStatusMessage": "datasetOnArchiveDisk"}} <br> PUT /api/v3/Datasets/{DatasetId}
    deactivate J
  end 
  loop Retry
    activate J
    J -->> S: {"jobStatusMessage": "finishedSuccessful"} <br>PUT /api/v3/Jobs/{JobId}
    deactivate J
  end 
```

### Retrieval Task Chain

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant J as Worker
  participant R as Retrieval Storage
  participant S as SciCat
  participant LTS as LTS

  AS --) J: Create Retrieval Task JobID, DatasetID
  loop Retry
    activate J
      J -->> S: {"jobStatusMessage": "inProgress"}   <br> PUT /api/v3/Jobs/{JobId}
      J -->> S: {"datasetlifecycle": {"retrieveStatusMessage": "started"}}   <br> PUT /api/v3/Datasets/{DatasetId}
    deactivate J
  end
  critical
    activate J
    LTS -->> R: Task: Download Datablocks from LTS
    deactivate J
  end
  critical
    activate J
    J -->> R: Task: Validate Datablocks
    deactivate J
  end
  loop Retry
    activate J
    J -->> S: {"jobStatusMessage": "finishedSuccessful"}   <br> PUT /api/v3/Jobs/{JobId}
    J -->> S: {"datasetlifecycle":<br> {"retrieveStatusMessage": "datasetRetrieved"}}<br> PUT /api/v3/Datasets/{DatasetId}
    J -->> S: POST Retrieval URL <endpoint>
    deactivate J
  end 

```
