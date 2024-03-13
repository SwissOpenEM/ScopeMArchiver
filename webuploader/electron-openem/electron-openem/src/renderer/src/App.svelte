<script lang="ts" src="https://pyscript.net/releases/2024.1.1/core.js">
  import Button, { Group, Label } from '@smui/button'
  import List, { Item, Meta } from '@smui/list'
  import Checkbox from '@smui/checkbox'
  import { onMount } from 'svelte'

  async function doPost(object_name: string) {
    // var archive_url = `/fastapi/archiving`
    var archive_url = 'http://openem-dev.ethz.ch/fastapi/archiving'
    const res = await fetch(archive_url, {
      method: 'POST',
      body: JSON.stringify({
        filename: object_name
      }),
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const json = await res.json()
    var result = JSON.stringify(json)
    console.log(result)
  }

  function onCreateJob() {
    if (selected.length == 0) {
      console.log('nothing selected')
      return
    }
    for (let filename of selected) {
      doPost(filename)
    }
    console.log(`Create Jobs for ${selected}`)
  }
  let items = [
    { object_name: 'a' },
    { object_name: 'a' },
    { object_name: 'a' },
    { object_name: 'a' },
    { object_name: 'a' }
  ]
  let selected = []

  onMount(async function () {
    // var archivabl1_objects_url = '/fastapi/archivable_objects'
    // var archivable_objects_url = 'http://localhost:8000/archivable_objects'
    var archivable_objects_url = 'http://openem-dev.ethz.ch/fastapi/archivable_objects'
    try {
      const res = await fetch(archivable_objects_url, {
        method: 'GET'
      })
      console.log(res)
      const json = await res.json()
      items = json
      console.log(json)
    } catch {}

    // items = JSON.parse(json);
    // console.log(items);
  })

  let changeEvent: CustomEvent<{ changedIndices: number[] }> | null
  changeEvent = null

  import { Dashboard } from '@uppy/svelte'
  import Uppy from '@uppy/core'
  import AwsS3 from '@uppy/aws-s3'
  import '@uppy/core/dist/style.css'
  import '@uppy/dashboard/dist/style.css'

  import SparkMd5 from 'spark-md5'

  async function calculateMD5(chunk, callback) {
    if (!calculateChecksum) {
      callback('')
      return
    }
    var reader = new FileReader()
    reader.onloadend = function () {
      var hash = SparkMd5.ArrayBuffer.hash(reader.result, true)
      var hashb64 = btoa(hash)
      callback(hashb64)
    }
    reader.readAsArrayBuffer(chunk)
  }

  var host = location.hostname
  host = 'openem-dev.ethz.ch'

  const uppy = new Uppy().use(AwsS3, {
    shouldUseMultipart: (file) => file.size > 10 * 2 ** 20,
    getTemporarySecurityCredentials: true,
    companionUrl: 'http://' + host + '/companion',
    // https://github.com/transloadit/uppy/blob/dc9e7c795ee5ab95fbf242255ec1564fb2db5fb9/website/src/docs/aws-s3-multipart.md#prepareuploadpartsfile-partdata
    async prepareUploadParts(file, { uploadId, key, parts }) {
      const { number: partNumber, chunk: body } = parts[0]
      const plugin = uppy.getPlugin('AwsS3Multipart')

      return new Promise(async function (resolve, reject) {
        const { url } = await plugin.signPart(file, { uploadId, key, partNumber, body })

        calculateMD5(body, (hash) => {
          if (!calculateChecksum) {
            resolve({ presignedUrls: { [partNumber]: url } })
          }
          resolve({
            presignedUrls: { [partNumber]: url },
            headers: { [partNumber]: { 'Content-MD5': hash } }
          })
          reject({})
        })
      })
    }
  })

  let calculateChecksum = true
</script>

<h1>Open EM Network Data Uploader Service</h1>

<center>
  <Group variant="raised">
    <Button variant="outlined" href="/minio/browser" class="button-shaped-round" target="_blank">
      <Label>Minio</Label>
    </Button>

    <Button variant="outlined" class="button-shaped-round" href="/traefik" target="_blank">
      <Label>Traefik Dashboard</Label>
    </Button>

    <Button variant="outlined" class="button-shaped-round" href="grafana" target="_blank">
      <Label>Grafana</Label>
    </Button>

    <Button variant="outlined" class="button-shaped-round" href="rabbitmq/" target="_blank">
      <Label>RabbitMQ</Label>
    </Button>

    <Button variant="outlined" class="button-shaped-round" href="/celery-flower/" target="_blank">
      <Label>Celery Flower</Label>
    </Button>

    <Button variant="outlined" class="button-shaped-round" href="/celery-insights" target="_blank">
      <Label>Celery Insights</Label>
    </Button>
  </Group>
</center>

<div>
  <center>
    <Group variant="raised">
      <Button variant="outlined" class="button-shaped-round" href="/tusd-upload">
        <Label>TuS File Upload</Label>
      </Button>

      <Button variant="outlined" class="button-shaped-round" href="/s3-upload">
        <Label>S3 File Upload</Label>
      </Button>
    </Group>
  </center>
</div>
<!-- <Textfield variant="filled" bind:value={selectedFile} label="File Name"></Textfield> -->
<div class="float-container">
  <div class="float-child">
    <List class="list" checkList on:SMUIList:selectionChange={(event) => (changeEvent = event)}>
      {#each items as item}
        <div>
          <Item>
            <Label>{item.object_name}</Label>
            <Meta>
              <Checkbox bind:group={selected} value={item.object_name} />
            </Meta>
          </Item>
        </div>
      {/each}
    </List>
    <Button variant="outlined" class="button-shaped-round" on:click={onCreateJob}>
      <Label>Archive Selected Files</Label>
    </Button>
  </div>
  <div class="float-child">
    <h3>File Upload to Minio S3 Storage</h3>
    <label>
      <input type="checkbox" bind:checked={calculateChecksum} />
      Calculate Checksums
    </label>
    <Dashboard {uppy} showProgressDetails="true" />
  </div>
  <!-- <section class="pyscript">
    <py-script> from js import items console.log(itmes) </py-script>
    <script type="py" src="./main.py"></script>

    <button id="btn-new-game" py-click="">Extract Metadata</button>
  </section> -->
</div>

<head>
  <!-- Recommended meta tags -->
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1.0" />
  <!-- PyScript CSS -->
  <!-- <link rel="stylesheet" href="https://pyscript.net/releases/2024.2.1/core.css" /> -->
  <!-- This script tag bootstraps PyScript -->
  <script type="module" src="https://pyscript.net/releases/2024.2.1/core.js"></script>
</head>

<style>
  * :global(.list) {
    max-width: 1000px;
    flex: 1;
    overflow: auto;
    max-height: 600px;
    margin-top: 25px;
    margin-bottom: 25px;
  }

  .float-container {
    border: 3px solid #fff;
    padding: 20px;
    float: left;
  }

  .float-child {
    width: 50%;
    float: left;
    padding: 20px;
  }
</style>
