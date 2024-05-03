package main

import (
	"context"
	"fmt"
	"io/fs"
	"log"
	"math"
	"os"
	"path"
	"time"

	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type SelectedFolder struct {
	files  []fs.DirEntry
	folder string
}

// App struct
type App struct {
	ctx context.Context

	folders map[string]SelectedFolder // Datastructure to store all the upload requests

	folderInputChannel chan UploadRequest // Requests to upload data are put into this channel
	errorChannel       chan string        // the go routine puts the error of the upload here
	resultChannel      chan string        // The result of the upload is put into this channel
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{}
}

// Show prompt before closing the app
func (b *App) beforeClose(ctx context.Context) (prevent bool) {
	dialog, err := runtime.MessageDialog(ctx, runtime.MessageDialogOptions{
		Type:    runtime.QuestionDialog,
		Title:   "Quit?",
		Message: "Are you sure you want to quit? This will stop all pending downloads.",
	})

	if err != nil {
		return false
	}
	return dialog != "Yes"
}

// Struct used to schedule an upload
type UploadRequest struct {
	id          string
	folder      string
	endpoint    string
	bucket      string
	md5checksum bool
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx

	a.folders = make(map[string]SelectedFolder)

	a.folderInputChannel = make(chan UploadRequest)
	a.resultChannel = make(chan string)

	// start multiple go routines/workers that will listen on the input channel
	numWorkers := 2
	for w := 1; w <= numWorkers; w++ {
		go a.uploadWorker()
	}
}

// Go routine that listens on the channel continously for upload requests and executes uploads.
func (a *App) uploadWorker() {
	for uploadRequest := range a.folderInputChannel {
		result := a.Upload(uploadRequest.endpoint, uploadRequest.bucket, uploadRequest.id, uploadRequest.md5checksum)
		a.resultChannel <- result
	}
}

// Select a folder using a native menu
func (a *App) SelectFolder() {
	dialogOptions := runtime.OpenDialogOptions{}

	folder, err := runtime.OpenDirectoryDialog(a.ctx, dialogOptions)
	if err != nil || folder == "" {
		return
	}

	files, err := os.ReadDir(folder)
	if err != nil {
		log.Fatal(err)
		return
	}

	id := uuid.New().String()

	a.folders[id] = SelectedFolder{folder: folder, files: files}

	for _, file := range files {
		fmt.Println(file.Name())
	}
	runtime.EventsEmit(a.ctx, "folder-added", id, folder)
}

// Progress notifier object for Minio upload
type ProgressNotifier struct {
	total_file_size     int64
	current_size        int64
	files_count         int
	current_file        int
	ctx                 context.Context
	previous_percentage float64
	start_time          time.Time
	id                  string
}

// Callback that gets called by fputobject.
// Note: does not work for multipart uploads
func (pn ProgressNotifier) Read(p []byte) (n int, err error) {
	n = len(p)
	pn.current_size += int64(n)

	current_percentage := float64(pn.current_size) / float64(pn.total_file_size)
	runtime.EventsEmit(pn.ctx, "progress-update", pn.id, current_percentage, pn.current_file, pn.files_count, time.Since(pn.start_time).Seconds())
	return
}

func (a *App) RemoveUpload(id string) {
	delete(a.folders, id)
	runtime.EventsEmit(a.ctx, "folder-removed", id)
}

func (a *App) ScheduleUpload(id string, endpoint string, bucket string, md5checksum bool) {

	selectedFolder, err := a.folders[id]
	if !err {
		fmt.Println("Scheduling upload failed for: ", selectedFolder.folder, id)
		return
	}

	// Go routine to handle result and errors
	go func() {
		select {
		case msg := <-a.resultChannel:
			fmt.Println("Upload finished: ", msg)
		case err := <-a.errorChannel:
			fmt.Println("Upload failed: ", err)
		}
	}()

	// Go routine to schedule the upload asynchronously
	go func() {
		fmt.Println("Scheduled upload for: ", selectedFolder.folder)
		runtime.EventsEmit(a.ctx, "upload-scheduled", id)
		// this channel is read by the go routines that does the actual upload
		a.folderInputChannel <- UploadRequest{id, selectedFolder.folder, endpoint, bucket, md5checksum}
	}()

}

// Upload all files in a folder to a minio bucket
func (a *App) Upload(endpoint string, bucket string, id string, md5checksum bool) string {
	accessKeyID := "minioadmin"
	secretAccessKey := "minioadmin"
	useSSL := false

	folder, e := a.folders[id]
	if !e {
		fmt.Println("Cannot find: ", id)
		return fmt.Sprintf("failed %s", id)
	}

	log.Printf("Using endpoint %s\n", endpoint)
	// Initialize minio client object.
	minioClient, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKeyID, secretAccessKey, ""),
		Secure: useSSL,
	})

	if err != nil {
		log.Fatalln(err)
	}

	// Make a new bucket called testbucket.
	bucketName := bucket
	location := "eu-west-1"

	err = minioClient.MakeBucket(a.ctx, bucketName, minio.MakeBucketOptions{Region: location})
	if err != nil {
		// Check to see if we already own this bucket (which happens if you run this twice)
		exists, errBucketExists := minioClient.BucketExists(a.ctx, bucketName)
		if errBucketExists == nil && exists {
			log.Printf("We already own %s\n", bucketName)
		} else {
			log.Fatalln(err)
		}
	} else {
		log.Printf("Successfully created %s\n", bucketName)
	}

	contentType := "application/octet-stream"

	pn := ProgressNotifier{files_count: len(folder.files), ctx: a.ctx, previous_percentage: 0.0, start_time: time.Now(), id: id}

	for idx, f := range folder.files {

		filePath := path.Join(folder.folder, f.Name())
		objectName := f.Name()

		pn.current_file = idx + 1
		fileinfo, _ := os.Stat(filePath)
		pn.total_file_size = fileinfo.Size()

		log.Printf("progress: %d of %d", pn.current_file, pn.files_count)

		runtime.EventsEmit(a.ctx, "progress-update", id, 0.0, pn.current_file, pn.files_count)

		_, err := minioClient.FPutObject(a.ctx, bucketName, objectName, filePath, minio.PutObjectOptions{
			ContentType:           contentType,
			Progress:              pn,
			SendContentMd5:        true,
			NumThreads:            4,
			DisableMultipart:      false,
			ConcurrentStreamParts: true,
		})
		if err != nil {
			log.Fatalln(err)
		}
	}

	elapsed := math.Floor(time.Since(pn.start_time).Seconds())
	runtime.EventsEmit(a.ctx, "upload-completed", id, elapsed)
	return fmt.Sprintf("Successfully uploaded %d files", len(folder.files))
}
