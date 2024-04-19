<script lang="ts">
  // import logo from "./assets/images/logo-universal.png";
  import logo from "./assets/images/logo-wide-1024x317.png";
  import { Upload } from "../wailsjs/go/main/App.js";
  import { SelectFolder, ClearSelection } from "../wailsjs/go/main/App.js";
  import List from "./List.svelte";
  import ListElement from "./ListElement.svelte";
  import { EventsOn } from "../wailsjs/runtime/runtime";

  let resultText: string = "";
  let minio_host: string = "localhost:9000";

  let items = [{ value: "<Please Select Items>", component: ListElement }];
  function selectFolder(): void {
    SelectFolder().then((result: Array<string>) => {});
  }
  function clearSelection(): void {
    ClearSelection();
    items = [];
    resultText = "";
  }

  EventsOn("files-added", (file_names: string[]) => {
    items = [];
    for (let r in file_names) {
      items.push({ value: file_names[r], component: ListElement });
    }
  });

  EventsOn(
    "progress-update",
    (current_percentage, current_file, total_files) => {
      resultText = `${(current_percentage * 100).toFixed(4)} % of file ${current_file} out of ${total_files}`;
      console.log(resultText);
    },
  );

  function upload(): void {
    Upload(minio_host).then((result) => {
      resultText = result;
    });
  }
</script>

<main>
  <img alt="Wails logo" id="logo" src={logo} />
  <div>
    <button class="btn" on:click={selectFolder}>Select</button>
    <button class="btn" on:click={clearSelection}>Clear</button>
    <div>
      <List {items} />
    </div>
  </div>
  <div class="input-box" id="input">
    <input
      autocomplete="off"
      bind:value={minio_host}
      class="input"
      id="name"
      type="text"
    />
    <button class="btn" on:click={upload}>Upload</button>
    <div class="result" id="result">{resultText}</div>
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
    width: 60px;
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
