# [Archival Flow](../backend/archiver/flows/archive_datasets_flow.py)

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
