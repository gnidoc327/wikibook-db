from fastapi import HTTPException, Request
from starlette.responses import JSONResponse


def custom_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})
