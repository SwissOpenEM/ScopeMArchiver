# [Retrieval Flow](../backend/archiver/flows/retrieve_datasets_flow.py)

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

- High level concepts
  - Flow
  - Task
  - error handling
  - storage (buckets, scratch, LTS) 
- Configuration
- Checksum Verification
- Concurrency
- interaction with LTS (timeouts, wait, wait for free storage)