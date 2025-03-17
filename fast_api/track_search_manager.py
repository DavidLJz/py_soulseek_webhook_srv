from collections import namedtuple

from app.infra.slsk import (
    SoulSeekClient,
    SearchResultEvent,
    slsk_search_request
)

from app.infra.websockets import ConnectionManager

from .models import tracks_info_from_aiosk_search_results, TrackInfo

SearchIndex = namedtuple('SearchIndex', ['query', 'ticket'])


class TrackSearchSessionManager:
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

    async def register_search_request(self, query: str) -> tuple[str, int, set[TrackInfo]]:
        for search_index in self._tracksets.keys():
            if search_index.query == query:
                return search_index.query, search_index.ticket, self._trackset_by_search(search_index)

        search_request = await slsk_search_request(self.slsk, query)

        search_index = SearchIndex(query=search_request.query, ticket=search_request.ticket)

        s = self._tracksets.setdefault(search_index, set())

        return search_request.query, search_request.ticket, s

    async def on_search_result_event(self, e: SearchResultEvent):
        search_index = SearchIndex(query=e.query.query, ticket=e.query.ticket)

        self._tracksets.setdefault(search_index, set())

        for r in e.query.results:
            for tt in tracks_info_from_aiosk_search_results(r):
                if not tt or tt in self._trackset_by_search(search_index):
                    continue

                self._trackset_by_search(search_index).add(tt)

                await self.manager.broadcast(tt.model_dump_json())

        n = len(self._trackset_by_search(search_index))

        await self.manager.broadcast(f"Tracks reported so far: {n}")
