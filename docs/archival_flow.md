# [Archival Flow](../backend/archiver/flows/archive_datasets_flow.py)

Archival is split into two subflows, `Create datablocks` and  `Move datablocks to LTS`An archival task can contain multiple datasets; for simplicity the case with only one is depicted here.

## Nomenclature

| Identifier   | Description                                                                                        |
|--------------|----------------------------------------------------------------------------------------------------|
| Flow         | Sequence of tasks and subflows                                                                     |
| Subflow      | Flow triggered by a parent flow                                                                    |
| Job          | A Scicat terminology corresponding to a archival flow; may contain multiple datasets as parameters |
| Archive Flow | Subflow that runs archiving for one dataset                                                        |
| User Error   | Scicat terminology for errors triggered by the user, e.g. dataset is incomplete; dataset not found |
| System Error | Scicat terminiolgy for unrecoverable (transient) error in the system                               |

## Critical Sections

A sequence of tasks that need to succeed atomically (all succeed or all are rolled back) are depicted as critical tasks below. They have a specific error handling associated in order to roll back all the task in that sequence.

## Retries

All task interacting with external services (i.e. Scicat) have retries implemented. Since they are not done in a task level but on the http request level, they are not depicted below.

Reading from the LTS has retries implemented on a task level and is therefore depicted below.

## Sequence Diagram

The digramm below shows the different steps in the archiving flow. Each step executed by the `Worker` is implemented as its own task (expect steps executed in error handling).

```mermaid
sequenceDiagram
  autonumber
  participant AS as Archival Service
  participant L as Landing Zone
  participant W as Worker
  participant ST as Staging
  participant S as SciCat
  participant LTS as LTS


  Note over AS, S: Subflow: Create datablocks

  S --) AS: Archive: POST /api/v1/jobs
  Note right of AS: Job {"id" : "id", "type":"archive", "datasetlist": [], ... } as defined in Scicat

  AS --) W: Create archival flow for each dataset
  Note left of S: {"uuid": "<flow uuid>", "name": "<flow name>"}, 
  AS -->> S: Respond to Scicat
  
        W --) S: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "inProgress"}, 
  
  critical Job for datasetlist
    Note over L,LTS: Subflow: Move dataset to LTS
  critical Subflow for {DatasetId}
              W --) S:  PATCH /api/v4/Dataset/{DatasetId}
              Note left of S: {"datasetlifecycle": {"archiveStatusMessage": "started"}}  
              W --> S: GET /api/v4/Datasets/{dataset_id}/origdatablocks
        W -->> L: Create datablocks
        L -->> ST: Move datablocks to staging
        loop Retry: Exponential backoff
          W -->> S: Register datablocks POST /api/v4/Datasets/{DatasetId}/datablocks
        end
        W -->> L: Cleanup dataset files, datablocks
        Note right of L: Dataset files only get cleaned up when everythings succeeds
    option Failure user error
        W --) S: Report error: PATCH /api/v4/Dataset/{DatasetId}
        Note left of S: {"datasetlifecycle:{"archiveStatusMessage": "missingFileserror", "archivable": False, "retrievable":False}}
        W -->> ST: Cleanup Datablocks
        W -->> L: Cleanup Datablocks
        Note right of L: No cleanup of dataset files
    option Failure system error
        W --) S: Report error: PATCH /api/v4/Dataset/{DatasetId}
        Note left of S: {"datasetlifecycle:{"archiveStatusMessage": "scheduleArchiveJobFailed", "archivable": "false", "retrievable":"false"}}
        W -->> ST: Cleanup datablocks
        W -->> L: Cleanup datablocks
        Note right of L: No cleanup of dataset files
    end
    option Failure user error
        W --) S: Report error: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "finishedWithDataseterrors"}
    option Failure system error
        W --) S: Report error: PATCH /api/v4/Jobs/{JobId}
        Note left of S: {"jobStatusMessage": "finishedUnsuccessful"}
  end
Note over W, LTS: Subflow: Move datablocks to LTS
loop for each datablock 
  critical
      ST -->> LTS: Move datablock to LTS
      ST -->> LTS: Verify checksum of datablock to LTS with retries
  option Moving datablock to LTS Failed
      W -->> LTS: Cleanup LTS folder
      W -->> S: Report error
      Note left of S: {"jobStatusMessage": "scheduleArchiveJobFailed"}
  end
  critical
      W -->> LTS: Verify datablock in LTS
      W -->> L: Cleanup dataset files, datablock
  option Datablock validation failed
      W -->> S: Report error
      Note left of S: {"jobStatusMessage": "scheduleArchiveJobFailed"}
      W -->> LTS: Cleanup datablocks
  end
end
    W -->> S:  PATCH /api/v4/Datasets/{DatasetId}
    Note left of S: {"datasetlifecycle": {"archivable": False, "retrievable": True, "archiveStatusMessage": "datasetOnArchiveDisk"}} 
    W -->> S: PATCH /api/v4/Jobs/{JobId}
    Note left of S: {"jobStatusMessage": "finishedSuccessful"} 
```
