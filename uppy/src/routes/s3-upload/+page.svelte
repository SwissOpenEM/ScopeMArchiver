<script lang="ts">
	// /** @type {import('./$types').PageData} */
	// export let data;

	import { Dashboard } from '@uppy/svelte';
	import Uppy from '@uppy/core';
	import AwsS3 from '@uppy/aws-s3';
	import '@uppy/core/dist/style.css';
	import '@uppy/dashboard/dist/style.css';

	import CryptoJS from 'crypto-js'

	async function calculateMD5(chunk, callback) {
		console.log("Calcualting hash")
		var reader = new FileReader();
		reader.onloadend = function () {
			var  hash = CryptoJS.MD5(CryptoJS.lib.WordArray.create(reader.result));
			var hashb64 = hash.toString(CryptoJS.enc.Base64)
			callback(hashb64);
		}
		reader.readAsArrayBuffer(chunk);
    };

	const uppy = new Uppy()
		.use(AwsS3, {
			shouldUseMultipart: (file) => file.size > 10 * 2 ** 20,
			companionUrl: 'http://openem-dev.ethz.ch/companion',
			// https://github.com/transloadit/uppy/blob/dc9e7c795ee5ab95fbf242255ec1564fb2db5fb9/website/src/docs/aws-s3-multipart.md#prepareuploadpartsfile-partdata
			async prepareUploadParts(file, { uploadId, key, parts, signal }) {
				const { number: partNumber, chunk: body } = parts[0]
				const plugin = uppy.getPlugin('AwsS3Multipart')

				return new Promise(async function(resolve, reject){

					const { url } = await plugin.signPart(file, { uploadId, key, partNumber, body, signal })

					calculateMD5(body, (hash) => {
						console.log("PartNumber:", partNumber,"hash: ", hash)
					 	resolve({presignedUrls: { [partNumber]: url }, headers: {[partNumber]:{"Content-MD5":hash}} })
					});
					
				})
				},
		});

	let showInlineDashboard = true;
</script>

<main>
    <h1>File Upload to Minio S3 Storage</h1>
	<label>
		<input type="checkbox" bind:checked={showInlineDashboard} />
		Show Dashboard
	</label>
	{#if showInlineDashboard}
		<Dashboard {uppy} />
	{/if}
</main>
