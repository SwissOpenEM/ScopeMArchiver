<script lang="ts">
	import Button, { Group, Label } from '@smui/button';
</script>

<h1>Open EM Network Data Uploader Service</h1>

<center>
	<Group variant="raised">
		<Button href="/minio/browser" target="_blank" class="button-shaped-round">
			<Label>Minio</Label>
		</Button>

		<Button
			variant="outlined"
			class="button-shaped-round"
			href="/traefik"
			target="_blank"
		>
			<Label>Traefik</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="grafana">
			<Label>Grafana</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="/s3-upload">
			<Label>File Upload to Minio</Label>
		</Button>
	</Group>
</center>



