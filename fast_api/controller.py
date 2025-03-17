from contextlib import asynccontextmanager
from decouple import config
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

import asyncio

from app.infra.slsk import (
	SoulSeekClient,
	SearchResultEvent,
	SessionDestroyedEvent,
	get_slsk_client,
	register_search_result_event,
	register_session_destroyed_event,
	slsk_start_track_transfer
  )

from app.infra.websockets import ConnectionManager

from .models import (
	WebsocketClientMessage, WebsocketServerMessage,
	WebsocketClientMessageType, WebsocketServerMessageType
	)

from .track_search_manager import TrackSearchSessionManager

public_router = APIRouter()

slsk : SoulSeekClient = None
manager : ConnectionManager = None
track_search_manager : TrackSearchSessionManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
	global slsk, manager, track_search_manager

	slsk = await get_slsk_client(
		username= config('SLSK_USERNAME'),
		password= config('SLSK_PASSWORD')
	)

	await slsk.start()
	await slsk.login()

	manager = ConnectionManager()

	track_search_manager = TrackSearchSessionManager(manager, slsk)

	async def on_search_result(result: SearchResultEvent):
		await track_search_manager.on_search_result_event(result)

	register_search_result_event(slsk, on_search_result)

	# register_session_destroyed_event(slsk, lambda e: asyncio.create_task(app.state.lifespan.shutdown()))

	async def reconnect_session(e: SessionDestroyedEvent):
		await slsk.login()

	register_session_destroyed_event(slsk, reconnect_session)

	async def on_new_connection(_, ws: WebSocket):
		msg = WebsocketServerMessage.from_ws_server_message_enum().model_dump_json()
		await ws.send_text(msg)

	manager.register_connection_event_listener(on_new_connection)

	yield

	await asyncio.gather(
		slsk.stop(),
		manager.disconnect_all()
	)


@public_router.get("/")
async def get():
	with open("../../../public/front/index.html") as f:
		return HTMLResponse(content=f.read(), status_code=200)


async def handle_track_download_request(websocket: WebSocket, ticket: int, username: str, filename: str):
	from aioslsk.transfer.model import TransferState

	transfer = await slsk_start_track_transfer(slsk, ticket, username, filename)
	
	await manager.send_personal_message(f"Downloading {filename} from {username}...", websocket)

	# Wait for the transfer to finish
	while not transfer.is_finalized():
		await asyncio.sleep(5)

	if transfer.state == TransferState.FAILED:
		await manager.send_personal_message(f"Download of {filename} from {username} failed!", websocket)
		return

	elif transfer.state == TransferState.ABORTED:
		await manager.send_personal_message(f"Download of {filename} from {username} was cancelled!", websocket)
		return

	elif transfer.state == TransferState.COMPLETE:
		await manager.send_personal_message(f"Download of {filename} from {username} finished!", websocket)

		# Transfer transfer.local_path as binary
		with open(transfer.local_path, 'rb') as f:
			await websocket.send_bytes(f.read())

	# await manager.send_personal_message(f"Download of {filename} from {username} finished!", websocket)


@public_router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
	try:
		await manager.connect(websocket)

		while True:
			jsons = await websocket.receive_text()
			msg = None

			try:
				msg = WebsocketClientMessage.from_json(jsons)

			except Exception as e:
				msg = WebsocketServerMessage.from_bad_request(f"Error parsing message: {e}")

				await manager.send_personal_message(msg.model_dump_json(), websocket)

				break

			if msg.msg_type == WebsocketClientMessageType.SEARCH_REQUEST:
				query = msg.struct_data.query

				await track_search_manager.register_search_request(client_id, query)

			elif msg.msg_type == WebsocketClientMessage.TRACK_DOWNLOAD_REQUEST:
				pass

	except WebSocketDisconnect:
		await manager.disconnect(client_id)