# [Archival Flow](../backend/archiver/flows/archive_datasets_flow.py)

Archival is split into two subflows, `Create Datablocks` and  `Move Datablocks to LTS`, which can be triggered separately. An archival task can contain multiple datasets; for simplicity the case with only one is depicted here.

| Identifier   | Description                                   |
|--------------|-----------------------------------------------|
| Flow         | Sequence of tasks necessary for archiving     |
| Subflow      | Flow triggered by a parent flow               |
| Job          | Schedules flow for multiple datasets          |
| Archive Flow | Subflow that runs archiving for one dataset   |
| user error   | Dataset is incomplete, not found, ...         |
| system error | unrecoverable (transient) error in the system |

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

  AS --) J: Create archival flow for each dataset
  activate S
  AS -->> S: 
  S -->> S: Reply? scheduleForArchiving status? Already set?
  deactivate S

  loop Retry: exponential backoff
    activate J
      activate S
        J --) S: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "inProgress"}, 
      deactivate S
    deactivate J
  end
  deactivate AS
  
  critical Job for datasetlist
    Note over L,LTS: Move dataset to LTS
  critical Subflow for {DatasetId}
      activate J
        loop Retry: exponential backoff
          activate J
            activate S
              J --) S:  PATCH /api/v4/Dataset/{DatasetId}
              Note left of S: {"datasetlifecycle": {"archiveStatusMessage": "started"}}  
            deactivate S
          deactivate J
        end
        loop Retry: exponential backoff
          activate J
            activate S
              J --> S: GET /api/v4/Datasets/{dataset_id}/origdatablocks
            deactivate S
          deactivate J
        end
        J -->> L: Create datablocks
        L -->> A: Move datablocks to staging
        loop Retry: Exponential backoff
          activate J
          J -->> S: Register datablocks POST /api/v4/Datasets/{DatasetId}/datablocks
          deactivate J
        end
        J -->> L: Cleanup dataset files, datablocks
        Note right of L: Dataset files only get cleaned up when everythings succeeds
      deactivate J
    option Failure user error
      activate J
        %% J --) S: Report error: PATCH /api/v4/Jobs/{JobId}
        %% Note left of S: {"jobStatusMessage": "finishedWithDataseterrors" ,<br>  "updatedAt": "...",<br>  "updatedBy": "..."}
        J --) S: Report error: PATCH /api/v4/Dataset/{DatasetId}
        Note left of S: {"datasetlifecycle:{"archiveStatusMessage": "missingFileserror", "archivable": False, "retrievable":False}}
        J -->> A: Cleanup Datablocks
        J -->> L: Cleanup Datablocks
        Note right of L: No cleanup of dataset files
      deactivate J
    option Failure system error
      activate J
        %% J --) S: Report error: PATCH /api/v4/Jobs/{JobId}
        %% Note left of S: {"jobStatusMessage": "finishedUnsuccessful",<br>  "updatedAt": "...",<br>  "updatedBy": "..."}
        J --) S: Report error: PATCH /api/v4/Dataset/{DatasetId}
        Note left of S: {"datasetlifecycle:{"archiveStatusMessage": "scheduleArchiveJobFailed", "archivable": "false", "retrievable":"false"}}
        J -->> A: Cleanup datablocks
        J -->> L: Cleanup datablocks
        Note right of L: No cleanup of dataset files
      deactivate J
    end
    option Failure user error
      activate J
        J --) S: Report error: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "finishedWithDataseterrors"}
      deactivate J
    option Failure system error
      activate J
        J --) S: Report error: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "finishedUnsuccessful"}
      deactivate J
  end
Note over J, LTS: Subflow `Move Datablocks to LTS`
loop for each datablock 
  critical
    activate J
      A -->> LTS: Move datablock to LTS
      A -->> A: Sleep for ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S seconds
      loop Retry: Exponential backoff
        A -->> LTS: Verify checksum of datablock to LTS
      end
    deactivate J
  option Moving datablock to LTS Failed
      activate J
      J -->> LTS: Cleanup LTS folder
      J -->> S: Report error
      Note left of S: {"jobStatusMessage": "scheduleArchiveJobFailed"}
      deactivate J
  end
  critical
      J -->> LTS: Verify datablock in LTS
      J -->> L: Cleanup dataset files, datablock
  option Datablock validation failed
      activate J
      J -->> S: Report error
      Note left of S: {"jobStatusMessage": "scheduleArchiveJobFailed"}
      J -->> LTS: Cleanup datablocks
      deactivate J
  end
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
