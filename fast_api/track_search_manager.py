from collections import namedtuple

from app.infra.slsk import (
    SoulSeekClient,
    SearchResultEvent,
    slsk_search_request
)

from app.infra.websockets import ConnectionManager

from .models import (
    tracks_info_from_aiosk_search_results, 
    TrackInfo,
    WebsocketServerMessage
    )

SearchIndex = namedtuple('SearchIndex', ['query', 'ticket'])


class TrackSearchSessionManager:
    """
    Manages track search sessions, handling search requests and broadcasting search results.
    Attributes:
        manager (ConnectionManager): The connection manager for handling websocket connections.
        slsk (SoulSeekClient): The SoulSeek client for performing search requests.
    Methods:
        __init__(manager: ConnectionManager, slsk: SoulSeekClient):
            Initializes the TrackSearchSessionManager with a connection manager and a SoulSeek client.
        async register_search_request(query: str) -> tuple[str, int, set[TrackInfo]]:
            Registers a search request, performs the search, and broadcasts the search response.
        async on_search_result_event(e: SearchResultEvent):
            Handles search result events, updates the track sets, and broadcasts new search results.
        async broadcast_search_response(query: str, ticket: int, tracklist: list[TrackInfo]):
            Broadcasts the search response to all connected clients.
    """

    _tracksets: dict[SearchIndex, set[TrackInfo]] = {}
    # Variable that stores a map of track sets indexed by SearchIndex

    manager: ConnectionManager
    slsk: SoulSeekClient

    def __init__(self, manager: ConnectionManager, slsk: SoulSeekClient):
        self.manager = manager
        self.slsk = slsk

    def _trackset_by_search(self, search_index: SearchIndex):
        return self._tracksets.get(search_index, set())

    def _remove_trackset(self, search_index: SearchIndex):
        self._tracksets.pop(search_index, None)

    async def register_search_request(self, client_id:str, query: str) -> tuple[str, int, set[TrackInfo]]:
        for search_index, tracklist in self._tracksets.items():
            if search_index.query != query:
                continue

            await self.broadcast_search_response(query, search_index.ticket, tracklist, client_id= client_id)
            return

        search_request = await slsk_search_request(self.slsk, query)

        search_index = SearchIndex(query=search_request.query, ticket=search_request.ticket)

        s = self._tracksets.setdefault(search_index, set())

        await self.broadcast_search_response(search_index, s, client_id= client_id)

    async def on_search_result_event(self, e: SearchResultEvent):
        search_index = SearchIndex(query=e.query.query, ticket=e.query.ticket)

        self._tracksets.setdefault(search_index, set())

        newtracks = []

        for r in e.query.results:
            for tt in tracks_info_from_aiosk_search_results(r):
                if not tt or tt in self._trackset_by_search(search_index):
                    continue

                self._trackset_by_search(search_index).add(tt)

                newtracks.append(tt)

        if not newtracks:
            return

        await self.broadcast_search_response(search_index, newtracks)

    async def broadcast_search_response(self, 
                                        search_index: SearchIndex,
                                        tracklist: list[TrackInfo],
                                        client_id: str = ""
                                        ):
        total_results = len(self._trackset_by_search(search_index))

        msg = WebsocketServerMessage.from_search_response(
            query=  search_index.query,
            ticket= search_index.ticket,
            total_results=  total_results,
            resultset=  tracklist
            )
        
        s = msg.model_dump_json()

        if client_id:
            await self.manager.send_personal_message(s, client_id= client_id)
        else:
            await self.manager.broadcast(s)
