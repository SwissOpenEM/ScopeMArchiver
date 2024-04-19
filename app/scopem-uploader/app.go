package main

import (
	"context"
	"fmt"
	"io/fs"
	"log"
	"os"
	"path"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct
type App struct {
	ctx context.Context

	selectedFiles []fs.DirEntry
	folder        string
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{}
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// Greet returns a greeting for the given name
func (a *App) Greet(name string) string {
	return fmt.Sprintf("Hello %s, It's show time!", name)
}

func (a *App) SelectFolder() []string {
	dialogOptions := runtime.OpenDialogOptions{}
	folder, _ := runtime.OpenDirectoryDialog(a.ctx, dialogOptions)
	a.folder = folder

	files, err := os.ReadDir(folder)
	if err != nil {
		log.Fatal(err)
	}

	a.selectedFiles = files

	file_names := []string{}

	for _, file := range files {
		fmt.Println(file.Name())
		file_names = append(file_names, file.Name())
	}
	runtime.EventsEmit(a.ctx, "files-added", file_names)
	return file_names
}

type ProgressNotifier struct {
	total_file_size     int64
	current_size        int64
	files_count         int
	current_file        int
	ctx                 context.Context
	previous_percentage float64
}

func (pn ProgressNotifier) Read(p []byte) (n int, err error) {
	n = len(p)
	pn.current_size += int64(n)

	current_percentage := float64(pn.current_size) / float64(pn.total_file_size)
	if current_percentage-pn.previous_percentage > 0.05 {
		pn.previous_percentage = current_percentage
		runtime.EventsEmit(pn.ctx, "progress-update", current_percentage, pn.current_file, pn.files_count)
	}
	return
}

func (a *App) ClearSelection() {
	a.selectedFiles = []fs.DirEntry{}
	a.folder = ""
}

func (a *App) Upload(endpoint string) string {
	accessKeyID := "minioadmin"
	secretAccessKey := "minioadmin"
	useSSL := false

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
	bucketName := "go-minio-testbucket"
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

	// Upload the test file
	// Change the value of filePath if the file is in another location
	// objectName := "file1_10GB.img"
	// filePath := "./file1_10GB.img"
	contentType := "application/octet-stream"

	pn := ProgressNotifier{files_count: len(a.selectedFiles), ctx: a.ctx, previous_percentage: 0.0}

	for idx, f := range a.selectedFiles {

		filePath := path.Join(a.folder, f.Name())
		objectName := f.Name()

		pn.current_file = idx + 1
		fileinfo, _ := os.Stat(filePath)
		pn.total_file_size = fileinfo.Size()

		runtime.EventsEmit(a.ctx, "progress-update", 0.0, pn.current_file, pn.files_count)

		_, err := minioClient.FPutObject(a.ctx, bucketName, objectName, filePath, minio.PutObjectOptions{ContentType: contentType, Progress: pn})
		if err != nil {
			log.Fatalln(err)
		}
	}

	// Upload the test file with FPutObject

	return fmt.Sprintf("Successfully uploaded %d files", len(a.selectedFiles))

}
