<script lang="ts">
	import Button, { Group, Label } from '@smui/button';
</script>

<h1>Open EM Network Data Uploader Service</h1>

<center>
	<Group variant="raised">
		<Button href="http://openem-dev.ethz.ch/minio/browser" target="_blank" class="button-shaped-round">
			<Label>Minio</Label>
		</Button>

		<Button
			variant="outlined"
			class="button-shaped-round"
			href="http://openem-dev.ethz.ch/traefik"
			target="_blank"
		>
			<Label>Traefik</Label>
		</Button>

		<Button variant="outlined" class="button-shaped-round" href="http://openem-dev.ethz.ch/grafana">
			<Label>Grafana</Label>
		</Button>

		<!-- <Button variant="outlined" class="button-shaped-round" href="/tusd-upload">
			<Label>Tusd Upload</Label>
		</Button> -->

		<Button variant="outlined" class="button-shaped-round" href="/s3-upload">
			<Label>File Upload to Minio</Label>
		</Button>
	</Group>
</center>



