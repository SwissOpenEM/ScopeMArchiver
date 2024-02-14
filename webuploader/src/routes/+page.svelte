<script lang="ts">
	import Button, { Group, Label } from '@smui/button';
</script>

<h1>Open EM Network Data Uploader Service</h1>

<center>
	<Group variant="raised">
		<Button href="/minio/browser" target="_blank" class="button-shaped-round">
			<Label>Minio</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="/traefik" target="_blank">
			<Label>Traefik Dashboard</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="grafana">
			<Label>Grafana</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="/tusd-upload">
			<Label>TuS File Upload</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="/s3-upload">
			<Label>S3 File Upload</Label>
		</Button>
	</Group>
</center>
