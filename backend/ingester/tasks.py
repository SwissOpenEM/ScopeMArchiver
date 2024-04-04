from celery import Celery, chain, shared_task
import time


@shared_task
def dummy_task():
    time.sleep(10)
