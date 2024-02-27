<script lang="ts">
	import Button, { Group, Label } from '@smui/button';
</script>

<h1>Open EM Network Data Uploader Service</h1>

<h2>Application</h2>
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
<h2>Infrastructure</h2>
<center>
	<Group variant="raised">
		<Button href="/minio/browser" class="button-shaped-round" target="_blank">
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
