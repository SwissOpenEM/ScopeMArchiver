# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.health_livez_get200_response import HealthLivezGet200Response
from openapi_server.models.health_livez_get503_response import HealthLivezGet503Response
from openapi_server.models.health_readyz_get200_response import HealthReadyzGet200Response
from openapi_server.models.health_readyz_get503_response import HealthReadyzGet503Response


class BaseHealthApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseHealthApi.subclasses = BaseHealthApi.subclasses + (cls,)
    async def health_livez_get(
        self,
    ) -> HealthLivezGet200Response:
        """Returns the health status of the service"""
        ...


    async def health_readyz_get(
        self,
    ) -> HealthReadyzGet200Response:
        """Returns the Readiness status of the service"""
        ...
