<script lang="ts">
	import Button, { Group, Label } from '@smui/button';
	import Textfield from '@smui/textfield';
	import List, { Item, Meta } from '@smui/list';
	import Checkbox from '@smui/checkbox';
	import { onMount } from 'svelte';

	async function doPost(object_name: Str) {
		var archive_url = `/fastapi/archiving`;
		// var archive_url = 'http://localhost:8000/archiving';
		const res = await fetch(archive_url, {
			method: 'POST',
			body: JSON.stringify({
				filename: object_name
			}),
			headers: {
				'Content-Type': 'application/json'
			}
		});

		const json = await res.json();
		var result = JSON.stringify(json);
		console.log(result);
	}

	function onCreateJob() {
		if (selected.length == 0) {
			console.log('nothing selected');
			return;
		}
		for (let filename of selected) {
			doPost(filename);
		}
		console.log(`Create Jobs for ${selected}`);
	}
	let items: List = [
		{ object_name: 'a' },
		{ object_name: 'a' },
		{ object_name: 'a' },
		{ object_name: 'a' },
		{ object_name: 'a' }
	];
	let selected: List = [];

	onMount(async function () {
		var archivable_objects_url = '/fastapi/archivable_objects';
		// var archivable_objects_url = 'http://localhost:8000/archivable_objects';
		try {
			const res = await fetch(archivable_objects_url, {
				method: 'GET'
			});
			console.log(res);
			const json = await res.json();
			items = json;
			console.log(json);
		} catch {}

		// items = JSON.parse(json);
		// console.log(items);
	});

	let changeEvent: CustomEvent<{ changedIndices: number[] }> | null;
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
<div>
	<center>
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
	</center>
</div>

<style>
	* :global(.list) {
		max-width: 1000px;
		flex: 1;
		overflow: auto;
		max-height: 300px;
		margin-top: 25px;
		margin-bottom: 25px;
	}
</style>
