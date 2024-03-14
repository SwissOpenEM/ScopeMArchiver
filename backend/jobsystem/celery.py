from celery import Celery
import os
import logging
from fastapi_featureflags import FeatureFlags, feature_flag, feature_enabled

FeatureFlags.load_conf_from_dict(dict(os.environ.items()))

if feature_enabled("ARCHIVER_ENABLED"):
    import archiver.tasks
if feature_enabled("INGESTER_ENABLED"):
    import ingester.tasks

_LOGGER = logging.getLogger("Jobs")

celery_app = Celery('tasks',
                    broker=os.environ.get('CELERY_BROKER_URL'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND'))
