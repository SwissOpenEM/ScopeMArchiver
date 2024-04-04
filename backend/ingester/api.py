from fastapi import APIRouter


from fastapi.responses import JSONResponse
import ingester.tasks as tasks

router = APIRouter()


@router.get("/ingester_test_route", status_code=200)
def test_route():
    return JSONResponse({"message": "hello"})


@router.get("/ingester_test_task", status_code=200)
def test_route():
    tasks.dummy_task.delay()
