# Archiving Flow

## Upload flow

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant S as Scicat
  participant A as Archiver Service

    C --> C: Select Dataset
    C --) S: Register Dataset: POST /Datasets
   activate S 
      Note left of S: { "isOnCentralDisk" : false, "archivable" : false, "archiveStatusMessage: "filesNotReadyYet"}
      S --) C: PID
   deactivate S
    C -->> A: Upload dataset
      Note left of A: Dataset
    C -->> S: PUT /Datasets/{datasetId}
      Note left of S: { "datasetlifecycle": {"archiveStatusMessage" : "datasetCreated, "archivable" : false, "archiveStatusMessage: "filesNotReadyYet"}}
    C -->> S: POST /api/v4/OrigDatablocks
      Note left of S: {fileBlock, "datasetId": "datasetId"}
    S -->> A: Trigger Archive Job: POST /api/v1/Job
      Note left of A: {}

```

- Source folder never used: why?
- Datafile list vs origdatablocks?


## [Archival Task Flow](./flows/archiving_flow.py)

Archival is split into two subflows, `Create Datablocks` and  `Move Datablocks to LTS`. That can be triggered separately.

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant L as Landing Zone
  participant J as Worker
  participant A as Staging
  participant S as SciCat
  participant LTS as LTS


  Note over AS, S: Subflow `Create Datablocks`

  S --) AS: Archive: POST /api/v1/jobs
  activate AS
  Note right of AS: Job {"id" : "id", "type":"archive", "datasetlist": [], ... } as defined in Scicat

  AS --) J: Create Archival Flow

  AS -->> S: Reply?
  Note left of S: {}
  deactivate AS
  loop Retry: Exponential backoff
    activate S
      J --) S: PATCH /api/v4/Jobs/{JobId}
      Note left of S: {"jobStatusMessage": "inProgress", "updatedAt": "...", "updatedBy": "..."}, 
    deactivate S
  end
  loop Retry: Exponential backoff
    activate J
      J --) S:  PATCH /api/v4/Dataset/{DatasetId}
      Note left of S: {"datasetlifecycle": {"archiveStatusMessage": "started"}, "updatedAt": "...", "updatedBy": "..."}  
    deactivate J
  end
  loop Retry: Exponential backoff
      J --> S: GET /api/v4/Datasets/{dataset_id}/origdatablocks
    activate S
      S --) J:sdf
      Note right of J: {""}, 
  end
  critical 
    activate J
      J -->> L: Create Datablocks
      L -->> A: Move Datablocks to Staging
      loop Retry: Exponential backoff
        activate J
        J -->> S: Register datablocks POST /api/v4/Datasets/{DatasetID}
        Note left of S: ?
        deactivate J
      end
      J -->> L: Cleanup Dataset files, Datablocks
      Note right of L: Dataset files only get cleaned up when everythings succeeds
    deactivate J
  option Failure
    activate J
      J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
      Note left of S: {"jobStatusMessage": "finishedWithDatasetErrors" Scicat specific?,<br>  "updatedAt": "...",<br>  "updatedBy": "...", <br> "jobResultObject" Storage specific?
      J --) S: Report Error: PATCH /api/v4/Dataset/{DatasetId}
      Note left of S: {"archiveStatusMessage": Scicat specific? valid values?<br>, "archiveReturnMessage": storage specific? free to choose?, <br> "updatedAt": "...", <br> "updatedBy": "..."}
      J -->> A: Cleanup Datablocks
      J -->> L: Cleanup Datablocks
      Note right of L: No cleanup of dataset files
    deactivate J
  end
  

  Note over J, LTS: Subflow `Move Datablocks to LTS`
    S -->> AS: Optional re-trigger from Scicat
    AS --) J: Create `Move datablock to LTS` Pipeline
  critical
    activate J
    A -->> LTS: Move Datablocks to LTS
    deactivate J
  option Move to LTS Failure
    activate J
    J -->> LTS: Cleanup LTS folder
    J -->> S: Report Error
    Note left of S: ?
    deactivate J
  end
  critical
    J -->> LTS:  Validate Datablocks in LTS
    J -->> L: Cleanup Dataset files, Datablocks
  option Validation Failure
    activate J
    J -->> S: Report Error
    Note left of S: ?
    J -->> LTS: Cleanup Datablocks
    deactivate J
  end
  loop Retry: Exponential backoff
    activate J
    J -->> S:  PATCH /api/v4/Datasets/{DatasetId}
    Note left of S: {"datasetlifecycle": {"retrievable": True, "archiveStatusMessage": "datasetOnArchiveDisk"}, <br> "updatedAt": "...", <br> "updatedBy": "..."} 
    deactivate J
  end 
  loop Retry: Exponential backoff
    activate J
    J -->> S: PATCH /api/v4/Jobs/{JobId}
    Note left of S: {"jobStatusMessage": "finishedSuccessful",<br>  "updatedAt": "...", <br> "updatedBy": "..."} 
    deactivate J
  end 
```

## [Retrieval Task Flow](./flows/retrieval_flow.py)

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant J as Worker
  participant R as Staging
  participant S as SciCat
  participant LTS as LTS

  activate AS
  S --) AS: Retrieve: POST /api/v1/jobs
  Note right of AS: Job {"id" : "id", "type":"retrieve", "datasetlist": [], ... } as defined in Scicat

  AS --) J: Create Retrieval Flow

  AS -->> S: Reply?
  Note left of S: {}
  deactivate AS 
  loop Retry: Exponential backoff
    activate J
      J -->> S: PATCH /api/v4/Jobs/{JobId}
      Note left of S: {"jobStatusMessage": "inProgress",<br> "updatedAt": "...", <br> "updatedBy": "..."}  
      J -->> S: PATCH /api/v4/Datasets/{DatasetId}
      Note left of S: {"datasetlifecycle": {"retrieveStatusMessage": "started"},<br> "updatedAt": "...", <br> "updatedBy": "..."}  
    deactivate J
  end
  critical
    activate J
      LTS -->> R: Download Datablocks from LTS
    deactivate J
  option Retrieval Failure
    activate J
      J --) S: Report Error: PATCH /api/v4/Dataset/{DatasetId}
          Note left of S: {"retrieveStatusMessage": Scicat specific? valid values?<br>, "retrieveReturnMessage": storage specific? free to choose?, <br> "updatedAt": "...", <br> "updatedBy": "..."}
      J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
         Note left of S: {"jobStatusMessage": "finishedWithDatasetErrors" Scicat specific?,<br>  "updatedAt": "...",<br>  "updatedBy": "...", <br> "jobResultObject" Storage specific?
      J -->> R: Cleanup Files
    deactivate J
  end
  critical
    activate J
    J -->> R: Validate Datablocks
    deactivate J
  option Validation Failure
    activate J
      J -->> S: Report Error ?
      J -->> R: Cleanup Files
    deactivate J
  end
  loop Retry: Exponential backoff
    activate J
      J -->> S: PATCH /api/v4/Jobs/{JobId}
      Note left of S: {"jobStatusMessage": "finishedSuccessful"} 
      J -->> S: PATCH /api/v4/Datasets/{DatasetId}
      Note left of S: {"datasetlifecycle":<br> {"retrieveStatusMessage": "datasetRetrieved"}} ? where to put download url? 
    deactivate J
  end 

```
