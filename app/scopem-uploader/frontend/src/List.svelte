<script>
  export let items;
</script>

<h3>Selected Files:</h3>
<div style="overflow-y: scroll; height:400px;">
  <ul>
    {#each items as item}
      <li>
        <svelte:component this={item.component} {...item} />
      </li>
    {/each}
  </ul>
</div>

<style>
  ul {
    list-style-type: none;
  }
</style>
