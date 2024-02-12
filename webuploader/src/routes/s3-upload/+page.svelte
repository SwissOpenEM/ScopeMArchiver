<script lang="ts">
	// /** @type {import('./$types').PageData} */
	// export let data;

	import { Dashboard } from '@uppy/svelte';
	import Uppy from '@uppy/core';
	import AwsS3 from '@uppy/aws-s3';
	import '@uppy/core/dist/style.css';
	import '@uppy/dashboard/dist/style.css';

	import SparkMd5 from 'spark-md5';

	async function calculateMD5(chunk, callback) {
		if(!calculateChecksum){
			callback("")
			return
		}
		var reader = new FileReader();
		reader.onloadend = function () {
			var hash = SparkMd5.ArrayBuffer.hash(reader.result, true)
			var hashb64 = btoa(hash)
			callback(hashb64);
		}
		reader.readAsArrayBuffer(chunk);
    };

	const uppy = new Uppy()
		.use(AwsS3, {
			shouldUseMultipart: (file) => file.size > 10 * 2 ** 20,
			getTemporarySecurityCredentials: true,
			companionUrl: 'http://openem-dev.ethz.ch/companion',
			// https://github.com/transloadit/uppy/blob/dc9e7c795ee5ab95fbf242255ec1564fb2db5fb9/website/src/docs/aws-s3-multipart.md#prepareuploadpartsfile-partdata
			async prepareUploadParts(file, { uploadId, key, parts, signal }) {
				const { number: partNumber, chunk: body } = parts[0]
				const plugin = uppy.getPlugin('AwsS3Multipart')

				return new Promise(async function(resolve, reject){

					const { url } = await plugin.signPart(file, { uploadId, key, partNumber, body, signal })

					calculateMD5(body, (hash) => {
						if(!calculateChecksum){
					 		resolve({presignedUrls: { [partNumber]: url }})
						}
					 	resolve({presignedUrls: { [partNumber]: url }, headers: {[partNumber]:{"Content-MD5":hash}} })
					});
					
				})
				},
		});

	let calculateChecksum = true;
</script>

<main>
    <h1>File Upload to Minio S3 Storage</h1>
	<label>
		<input type="checkbox" bind:checked={calculateChecksum} />
		Calculate Checksums
	</label>
		<Dashboard uppy={uppy}  showProgressDetails=true />
</main>
