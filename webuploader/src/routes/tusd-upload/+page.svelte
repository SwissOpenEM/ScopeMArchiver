<script lang="ts">
	// /** @type {import('./$types').PageData} */
	// export let data;

	import { Dashboard } from '@uppy/svelte';
	import Uppy from '@uppy/core';
	import Tus from '@uppy/tus';

	import '@uppy/core/dist/style.css';
	import '@uppy/dashboard/dist/style.css';

	const host = location.hostname;
	let tusd_url = 'http://' + host + '/tusd/files';

	let uppy = new Uppy().use(Tus, {
		endpoint: tusd_url
	});
</script>

<main>
	<h1>TusD File Upload</h1>
	<Dashboard {uppy} showProgressDetails="true" />
</main>
