<script lang="ts">
  // import logo from "./assets/images/logo-universal.png";
  import logo from "./assets/images/logo-wide-1024x317.png";
  import { Upload } from "../wailsjs/go/main/App.js";
  import {
    SelectFolder,
    RemoveUpload,
    ScheduleUpload,
  } from "../wailsjs/go/main/App.js";
  import List from "./List.svelte";
  import ListElement from "./ListElement.svelte";
  import { EventsOn } from "../wailsjs/runtime/runtime";
  import { v4 as uuidv4 } from "uuid";

  let minio_host: string = "openem-dev.ethz.ch:9000";
  let minio_bucket: string = "go-minio-testbucket";
  let md5checksum = false;

  let items = {};

  function newItem(id: string): string {
    items[id] = {
      value: "<Please Select Folder> ",
      id: id,
      status: "",
      progress: 0,
      selectFolder: selectFolder,
      removeUpload: removeUpload,
      scheduleUpload: scheduleUpload,
      component: ListElement,
    };
    items = items;
    return id;
  }

  function selectFolder(): void {
    SelectFolder();
  }

  function removeUpload(id: string): void {
    RemoveUpload(id);
  }

  function secondsToStr(elapsed_seconds): string {
    return new Date(elapsed_seconds * 1000).toISOString().substr(11, 8);
  }

  function scheduleUpload(id: string): void {
    ScheduleUpload(id, minio_host, minio_bucket);
  }

  EventsOn("folder-added", (id, folder) => {
    newItem(id);
    items[id].value = folder;
  });

  EventsOn("folder-removed", (id) => {
    delete items[id];
    items = items;
  });

  EventsOn("upload-scheduled", (id) => {
    items[id].status = "Scheduled";
  });

  EventsOn("upload-completed", (id, elapsed_seconds) => {
    items[id].status = "Completed in " + secondsToStr(elapsed_seconds);
  });

  EventsOn(
    "progress-update",
    (id, current_percentage, current_file, total_files, elapsed_seconds) => {
      const perc = (parseFloat(current_file) / parseFloat(total_files)) * 100;
      // items[id].progress = (parseFloat(current_percentage) * 100).toFixed(0);
      items[id].progress = perc.toFixed(0);
      items[id].status = "Uploading... " + secondsToStr(elapsed_seconds);
    },
  );
</script>

<main>
  <img alt="Wails logo" id="logo" src={logo} />
  <div class="input-box" id="input">
    <input
      autocomplete="off"
      bind:value={minio_host}
      class="input"
      id="name"
      type="text"
    />
    <input
      autocomplete="off"
      bind:value={minio_bucket}
      class="input"
      id="name"
      type="text"
    />
    <label>
      <input type="checkbox" bind:checked={md5checksum} />
      Send md5 checksum
    </label>
    <button
      class="btn"
      on:click={() => {
        selectFolder();
      }}>Add Folder</button
    >
  </div>
  <div>
    <div id="upload-list">
      <List {items} />
    </div>
  </div>
</main>

<style>
  #logo {
    display: block;
    width: 50%;
    height: 50%;
    margin: auto;
    padding: 10% 0 0;
    background-position: center;
    background-repeat: no-repeat;
    background-size: 100% 100%;
    background-origin: content-box;
  }

  .result {
    height: 20px;
    line-height: 20px;
    margin: 1.5rem auto;
  }

  .input-box .btn {
    width: 90px;
    height: 30px;
    line-height: 30px;
    border-radius: 3px;
    border: none;
    margin: 0 0 0 20px;
    padding: 0 8px;
    cursor: pointer;
  }

  .input-box .btn:hover {
    background-image: linear-gradient(to top, #cfd9df 0%, #e2ebf0 100%);
    color: #333333;
  }

  .input-box .input {
    border: none;
    border-radius: 3px;
    outline: none;
    height: 30px;
    line-height: 30px;
    padding: 0 10px;
    background-color: rgba(240, 240, 240, 1);
    -webkit-font-smoothing: antialiased;
  }

  .input-box .input:hover {
    border: none;
    background-color: rgba(255, 255, 255, 1);
  }

  .input-box .input:focus {
    border: none;
    background-color: rgba(255, 255, 255, 1);
  }
</style>
