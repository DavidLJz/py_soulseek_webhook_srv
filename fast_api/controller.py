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

from .models import WebsocketClientMessage, WebsocketServerMessage
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


async def handle_search_request(websocket: WebSocket, query: str):
	query, ticket, trackset = await track_search_manager.register_search_request(query)

	s = f'You searched: "{query}", ticket: {ticket}'

	await manager.send_personal_message(s, websocket)

	if len(trackset) > 0:
		for t in trackset:
			await manager.send_personal_message(t.model_dump_json(), websocket)
	else:
		await manager.send_personal_message('Waiting for search results...', websocket)


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



html = """
<!DOCTYPE html>
<html>
	<head>
		<title>Chat</title>
	</head>
	<body>
		<h1>WebSocket Chat</h1>
		<h2>Your ID: <span id="ws-id"></span></h2>
		<form action="" onsubmit="sendMessage(event)">
			<input type="text" id="messageText" autocomplete="off"/>
			<button>Send</button>
		</form>
		<div id='messages'>
		</div>
		<script>
			var client_id = Date.now()
			document.querySelector("#ws-id").textContent = client_id;
			var ws = new WebSocket(`ws://localhost:8000/ws/${client_id}/search`);
			ws.onmessage = function(event) {
				var messages = document.getElementById('messages')
				var message = document.createElement('div')
				var content = JSON.parse(event.data)
				message.innerHTML = `
					<div style="border: 1px solid black; margin: 10px; padding: 10px;">
						<div>Username: ${content.username}</div>
						<div>Filename: ${content.filename}</div>
						<div>Bitrate: ${content.bitrate}</div>
						<div>Sample Rate: ${content.sample_rate}</div>
						<div>Bit Depth: ${content.bit_depth}</div>
						<div>Duration: ${content.duration}</div>
						<button onclick="downloadFile()">Download</button>
					</div>
				`
				messages.appendChild(message)
			};
			function sendMessage(event) {
				var input = document.getElementById("messageText")
				
				const searchRequest = {
					query: input.value
				}
				
				ws.send( 
				input.value = ''
				event.preventDefault()
			}
			function downloadFile() {
				alert('Download button clicked!')
			}
		</script>
	</body>
</html>
"""

@public_router.get("/")
async def get():
	return HTMLResponse(html)


@public_router.websocket("/ws/{client_id}/search")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
	try:
		await manager.connect(websocket)

		while True:
			jsons = await websocket.receive_text()
			msg = None

			try:
				msg = WebsocketMessage.from_json(jsons)

			except Exception as e:
				await manager.send_personal_message(f"Error parsing message: {e}", websocket)

				continue

			if msg.msg_type == WebsocketClientMessage.SEARCH_REQUEST:
				await handle_search_request(websocket, msg.struct_data.query)
			
			elif msg.msg_type == WebsocketClientMessage.TRACK_DOWNLOAD_REQUEST:
				pass

	except WebSocketDisconnect:
		await manager.disconnect(websocket)
		await manager.broadcast(f"Client #{client_id} left the chat")