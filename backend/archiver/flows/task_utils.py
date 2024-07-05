from prefect.runtime import flow_run, task_run


def generate_task_name_dataset():
    task_name = task_run.task_name
    parameters = task_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{task_name}-dataset_id-{dataset_id}"


def generate_task_name_job():
    task_name = task_run.task_name
    parameters = task_run.get_parameters()
    job_id = parameters["job_id"]

    return f"{task_name}-job_id-{job_id}"


def generate_flow_name_dataset():
    flow_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{flow_name}-dataset_id-{dataset_id}"


def generate_flow_name_job_id():
    flow_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()
    job_id = parameters["job_id"]

    return f"{flow_name}-job_id-{job_id}"


def generate_subflow_run_name_job_id_dataset_id():
    flow_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{flow_name}-dataset_id-{dataset_id}"
