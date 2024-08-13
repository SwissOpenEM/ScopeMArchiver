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


## [Archival Task Flow](../backend/archiver/flows/archive_datasets_flow.py)

Archival is split into two subflows, `Create Datablocks` and  `Move Datablocks to LTS`, which can be triggered separately. An archival task can contain multiple datasets; for simplicity the case with only one is depicted here.

| Identifier   | Description                                   |
| ------------ | --------------------------------------------- |
| Flow         | Sequence of tasks necessary for archiving     |
| Subflow      | Flow triggered by a parent flow               |
| Job          | Schedules flow for multiple datasets          |
| Archive Flow | Subflow that runs archiving for one dataset   |
| User Error   | Dataset is incomplete, not found, ...         |
| System Error | unrecoverable (transient) error in the system |


```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant L as Landing Zone
  participant J as Worker
  participant A as Staging
  participant S as SciCat
  participant LTS as LTS


  %% Note over AS, S: Subflow `Create Datablocks`

  S --) AS: Archive: POST /api/v1/jobs
  activate AS
  Note right of AS: Job {"id" : "id", "type":"archive", "datasetlist": [], ... } as defined in Scicat

  AS --) J: Create Archival Flow for All Dataset
  activate S
  AS -->> S: 
  S -->> S: Reply? scheduleForArchiving status? Already set?
  deactivate S

  loop Retry: Exponential backoff
    activate J
      activate S
        J --) S: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "inProgress"}, 
      deactivate S
    deactivate J
  end
  deactivate AS
  
  critical Job for datasetlist
    critical Subflow for {DatasetIf}
      activate J
        loop Retry: Exponential backoff
          activate J
            activate S
              J --) S:  PATCH /api/v4/Dataset/{DatasetId}
              Note left of S: {"datasetlifecycle": {"archiveStatusMessage": "started"}}  
            deactivate S
          deactivate J
        end
        loop Retry: Exponential backoff
          activate J
            activate S
              J --> S: GET /api/v4/Datasets/{dataset_id}/origdatablocks
              S --) J:sdf
              Note right of J: {""}, 
            deactivate S
          deactivate J
        end
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
    option Failure User Error
      activate J
        %% J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
        %% Note left of S: {"jobStatusMessage": "finishedWithDatasetErrors" ,<br>  "updatedAt": "...",<br>  "updatedBy": "..."}
        J --) S: Report Error: PATCH /api/v4/Dataset/{DatasetId}
        Note left of S: {"datasetlifecycle:{"archiveStatusMessage": "missingFilesError", "archivable": False, "retrievable":False}}
        J -->> A: Cleanup Datablocks
        J -->> L: Cleanup Datablocks
        Note right of L: No cleanup of dataset files
      deactivate J
    option Failure System Error
      activate J
        %% J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
        %% Note left of S: {"jobStatusMessage": "finishedUnsuccessful",<br>  "updatedAt": "...",<br>  "updatedBy": "..."}
        J --) S: Report Error: PATCH /api/v4/Dataset/{DatasetId}
        Note left of S: {"datasetlifecycle:{"archiveStatusMessage": "scheduleArchiveJobFailed", "archivable": "false", "retrievable":"false"}}
        J -->> A: Cleanup Datablocks
        J -->> L: Cleanup Datablocks
        Note right of L: No cleanup of dataset files
      deactivate J
    end
    option Failure User Error
      activate J
        J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "finishedWithDatasetErrors"}
      deactivate J
    option Failure System Error
      activate J
        J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "finishedUnsuccessful"}
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
    Note left of S: {"datasetlifecycle": {"archivable": False, "retrievable": True, "archiveStatusMessage": "datasetOnArchiveDisk"}} 
    deactivate J
  end 
  loop Retry: Exponential backoff
    activate J
    J -->> S: PATCH /api/v4/Jobs/{JobId}
    Note left of S: {"jobStatusMessage": "finishedSuccessful"} 
    deactivate J
  end 
```

## [Retrieval Task Flow](../backend/archiver/flows/retrieve_datasets_flow.py)

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant J as Worker
  participant R as Staging
  participant S as SciCat
  participant LTS as LTS

  S --) AS: Retrieve: POST /api/v1/jobs
  activate AS
  Note right of AS: Job {"id" : "id", "type":"retrieve", "datasetlist": [], ... } as defined in Scicat
  AS --) J: Create Retrieval Flow
  AS -->> S: Reply?
  deactivate AS 
  Note left of S: {}
  loop Retry: Exponential backoff
    activate J
      J -->> S: PATCH /api/v4/Jobs/{JobId}
      Note left of S: {"jobStatusMessage": "inProgress"}  
      J -->> S: PATCH /api/v4/Datasets/{DatasetId}
      Note left of S: {"datasetlifecycle": {"retrieveStatusMessage": "started"}}  
    deactivate J
  end
  critical
    activate J
      LTS -->> R: Download Datablocks from LTS
    deactivate J
  option Retrieval Failure
    activate J
      J --) S: Report Error: PATCH /api/v4/Dataset/{DatasetId}
          Note left of S: {"retrieveStatusMessage": Scicat specific? valid values?<br>, "retrieveReturnMessage": "retrievalFailed"}
      J --) S: Report Error: PATCH /api/v4/Jobs/{JobId}
         Note left of S: {"jobStatusMessage": "finishedWithDatasetErrors" Scicat specific?, <br> "jobResultObject" Storage specific?
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
      Note left of S: {"datasetlifecycle":<br> {"retrieveStatusMessage": "datasetRetrieved", "retrievable": True}} 
    deactivate J
  end 

```

> Note: `updatedBy` and `updatedAt` are omitted for brevity but need to be set for every update of the job status and datsetlifecycle as well.

```mermaid
graph LR

    Job[Job ID] --> ScheduleJob{ScheduleFlows}
  subgraph parallel flows
    ScheduleJob --> Subflow1(Subflow Dataset ID 1)
    ScheduleJob --> Subflow2(Subflow Dataset ID 2)
  end
  subgraph Parallel move to LTS 2
  Subflow1 --> Move1{Schedule move}
  Move1 --> Task1(Task Datablock 1)
  Move1 --> Task2(Task Datablock 2)
  Move1 --> Task3(Task Datablock 3)
  Move1 --> Task4(Task Datablock 4)
  Task1 --> WaitMove{Wait move}
  Task2 --> WaitMove{Wait move}
  Task3 --> WaitMove{Wait move}
  Task4 --> WaitMove{Wait move}
  end
  subgraph Parallel move to LTS 1
  Subflow2--> Move2{Schedule move}
  Move2 --> Task21(Task Datablock 1)
  Move2 --> Task22(Task Datablock 2)
  Move2 --> Task23(Task Datablock 3)
  Move2 --> Task24(Task Datablock 4)
  Task21 --> WaitMove2{Wait move}
  Task22 --> WaitMove2{Wait move}
  Task23 --> WaitMove2{Wait move}
  Task24 --> WaitMove2{Wait move}
  end

  subgraph Sequential data verification

  WaitMove --> Verification{Schedule Verification}
  WaitMove2 --> Verification{Schedule Verification}

  Verification --> Verify11(Datablock 1)
  Verify11 --> Verify12(Datablock 2)
  Verify12 --> Verify13(Datablock 2)
  Verify13 --> Verify14(Datablock 2)
  Verify14 --> Verify21(Datablock 2)
  Verify21 --> Verify22(Datablock 2)
  Verify22 --> Verify23(Datablock 2)
  Verify23 --> Verify24(Datablock 2)
  end
```
