from prefect.runtime import flow_run, task_run


def generate_task_run_name_job_id():
    task_name = task_run.task_name

    parameters = task_run.parameters
    job_id = parameters["job_id"]

    return f"{task_name}-{job_id}"


def generate_flow_run_name_job_id():
    flow_name = flow_run.get_flow_name()

    parameters = flow_run.get_parameters()
    job_id = parameters["job_id"]

    return f"{flow_name}-{job_id}"


def generate_flow_run_name_dataset_id():
    flow_name = flow_run.get_flow_name()

    parameters = flow_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{flow_name}-{dataset_id}"


def generate_task_run_name_dataset_id():
    task_name = task_run.task_name

    parameters = task_run.parameters
    dataset_id = parameters["dataset_id"]

    return f"{task_name}-{dataset_id}"


class DatasetError(Exception):
    pass


class SystemError(Exception):
    pass
