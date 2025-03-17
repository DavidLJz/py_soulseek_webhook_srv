from decouple import config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from fast_api.controller import public_router, lifespan


app = FastAPI(
	title='Api',
	docs_url='/docs', 
	redoc_url='/redoc',
	openapi_url='/openapi.json',
	lifespan= lifespan
	)

origins = [
  "http://127.0.0.1:3000",
  "http://localhost:3000",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
  "http://localhost:8080",
  "http://10.10.6.221:8080"
]

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#   try:
#     start_time = time()
#     response = await call_next(request)
#     process_time = time() - start_time

#     logger.info( f"{request.method} {request.url} - {response.status_code} - {process_time:.2f}s")

#     return response

#   except Exception as e:
#     logger.exception(e)

#     raise e

# Handler of Unproccessable Entity Errors

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	
	def item_path_parser(item) -> str:
		if isinstance(item, int):
			return f"[{item}]"

		return f".{item}"
	
	errorlist = []

	for err in exc.errors():
		path = '$' + ''.join( item_path_parser(item) for item in err['loc'] )
		msg = err['msg']

		errorlist.append({"path": path, "msg": msg})

	return JSONResponse(
		status_code=422,
		content= errorlist
	)


app.include_router(public_router, prefix ='')


if __name__ == '__main__':
	import uvicorn
	import argparse

	parser = argparse.ArgumentParser(description= 'API Administración de Planeación')

	parser.add_argument('--host', type=str, help='Host de la API', default='0.0.0.0')
	parser.add_argument('--port', type=int, help='Puerto de la API', default=8000)
	parser.add_argument('--reload', action='store_true', help='Recargar la API al detectar cambios')

	parser.add_argument('--ssl_keyfile', default=None)
	parser.add_argument('--ssl_certfile', default=None)

	args = parser.parse_args()

	# uvicorn api:app --reload --port $port --host $host
	uvicorn.run('api:app', host=args.host, port=args.port, reload= args.reload, 
				ssl_keyfile= args.ssl_keyfile,
				ssl_certfile= args.ssl_certfile)
