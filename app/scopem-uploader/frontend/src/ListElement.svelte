<script>
  export let value;
  export let status;
  export let progress;
  export let selectFolder;
  export let removeUpload;
  export let scheduleUpload;
  export let id;
</script>

<div class="listitem">
  <div class="path">
    {value}
  </div>
  <div>
    {status}
  </div>
  <div>
    {progress} %
  </div>
  <div class="buttongrid">
    <button
      class="btn"
      on:click={() => {
        scheduleUpload(id);
      }}>Upload</button
    >
    <button
      class="btn"
      on:click={() => {
        removeUpload(id);
      }}>Clear</button
    >
  </div>
</div>

<style>
  .listitem {
    display: grid;
    grid-template-columns: 5fr 2fr 2fr 2fr;
    padding-right: 30px;
  }
  .buttongrid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
  .path {
    text-align: left;
  }
</style>
