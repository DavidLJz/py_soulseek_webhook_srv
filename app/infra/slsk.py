import asyncio
import sys
from pydantic import BaseModel

from typing import AsyncGenerator, Callable

from aioslsk.client import SoulSeekClient
from aioslsk.settings import Settings, CredentialsSettings
from aioslsk.search.model import SearchResult, SearchRequest, SearchQuery
from aioslsk.transfer.model import TransferRequest, Transfer
from aioslsk.events import SearchResultEvent, EventBus, SessionDestroyedEvent

class SoulseekAccesor:
    '''
    Example of usage:
    ```python
    await with SoulseekAccesor(slskconfig) as client:
        pass
    ```
    '''

    _client: SoulSeekClient
    _settings: Settings

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = SoulSeekClient(self._settings)

    async def __aenter__(self) -> SoulSeekClient:
        await self._client.start()
        await self._client.login()
        return self._client

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._client.stop()


async def get_slsk_client(username:str,
                          password:str, 
                          bus: EventBus|None = None) -> SoulSeekClient:
    '''
    Returns a non-initialized SoulSeekClient instance
    '''
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    s = Settings(
        credentials=CredentialsSettings(
        username= username,
        password= password,
        ),
    )

    client = SoulSeekClient(s, event_bus= bus)

    client.settings.searches.send.request_timeout = 10    
    client.settings.network.server.reconnect.auto = True

    return client


def register_session_destroyed_event(client: SoulSeekClient, callback: Callable[[SessionDestroyedEvent], None]):
    client.events.register(SessionDestroyedEvent, callback)


def register_search_result_event(client: SoulSeekClient, callback: Callable[[SearchResultEvent], None]):
    client.events.register(SearchResultEvent, callback)


async def slsk_search_request(client: SoulSeekClient, query: str) -> SearchRequest:
    return await client.searches.search(query)


async def slsk_start_track_transfer(client: SoulSeekClient, ticket: int, username: str, filename: str) -> Transfer:
    return await client.transfers.download(ticket, username, filename)