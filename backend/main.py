import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi_featureflags import FeatureFlags, feature_flag, feature_enabled

FeatureFlags.load_conf_from_dict(dict(os.environ.items()))

app = FastAPI(root_path=os.environ.get('API_ROOT_PATH', '/'))

if feature_enabled("ARCHIVER_ENABLED"):
    import archiver.api as archiver_api
    app.include_router(archiver_api.router)
if feature_enabled("INGESTER_ENABLED"):
    import ingester.api as ingester_api
    app.include_router(ingester_api.router)


origins = [
    "http://127.0.0.1*",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
