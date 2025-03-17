from enum import Enum
from json import loads
from typing import Any, Iterable
from pydantic import BaseModel

from aioslsk.search.model import FileData, SearchResult

# region TrackInfo

def aiosk_FileData_Attributes_to_TrackInfo_Attributes(attributes: list) -> dict:
  d = {
    'bitrate': None,
    'sample_rate': None,
    'bit_depth': None,
    'duration': None
  }

  # Index	Meaning	Usage
  # 0	bitrate	compressed
  # 1	length in seconds	compressed, lossless
  # 2	VBR	compressed
  # 4	sample rate	lossless
  # 5	bitness	lossless

  for a in attributes:
    k, v = a.key, a.value

    if k == 0:
      d['bitrate'] = int(v)
    elif k == 1:
      d['duration'] = int(v)
    elif k == 4:
      d['sample_rate'] = int(v)
    elif k == 5:
      d['bit_depth'] = int(v)

  return d


class TrackInfo(BaseModel):
  ticket: int
  username: str

  filename: str
  fullpath: str
  extension: str
  filesize: int = None
  attributes: dict = None

  bitrate: int|None = None
  sample_rate: int|None = None
  bit_depth: int|None = None
  duration: int|None = None

  class Config:
    schema_extra = {
    "example": {
      "filename": "The Beatles - Hey Jude.mp3",
      "extension": "mp3"
    }
    }

  @staticmethod
  def from_file_data(file_data: FileData, username:str, ticket:int) -> 'TrackInfo':
    filename = file_data.filename.split('\\')[-1]

    extension = file_data.extension

    if not extension:
      p = file_data.filename.split('.')

      if len(p) > 1:
        extension = p[-1]

      attrdict = aiosk_FileData_Attributes_to_TrackInfo_Attributes(file_data.attributes)

      return TrackInfo(
      **attrdict,
      ticket= ticket,
      username= username,
      filename= filename,
      fullpath= file_data.filename,
      extension= extension,
      filesize= file_data.filesize,
      )

  @property
  def duration_minutes(self):
    m = self.duration // 60
    s = self.duration % 60

    return f"{m}:{s:02d}"

  def __hash__(self):
    return hash((self.ticket, self.username, self.filename, self.fullpath, self.extension))


def tracks_info_from_aiosk_search_results(s: SearchResult):
  if not s.shared_items:
    return

  for r in s.shared_items:
    yield TrackInfo.from_file_data(r, username= s.username, ticket= s.ticket)

# endregion

# region Client

class WebsocketClientMessageType(Enum):
  SEARCH_REQUEST = 1
  TRACK_DOWNLOAD_REQUEST = 2


class SearchRequest(BaseModel):
  '''
  Represents a search request made by a user to the SoulSeek server. 
  Should not be confused with the SearchRequest class from the aioslsk library.
  '''

  query: str

  class Config:
    schema_extra = {
      "example": {
        "query": "The Beatles"
      }
    }


class TrackDownloadRequest(BaseModel):
  ticket: int
  username: str
  filename: str


class WebsocketClientMessage(BaseModel):
  msg_type: WebsocketClientMessageType
  data: dict

  @staticmethod
  def from_json(s:str) -> 'WebsocketClientMessage':
    d = loads(s)

    return WebsocketClientMessage(**d)

  @property
  def struct_data(self) -> SearchRequest|TrackDownloadRequest:
    if self.msg_type == WebsocketClientMessageType.SEARCH_REQUEST:
      return SearchRequest(**self.data)

    elif self.msg_type == WebsocketClientMessageType.TRACK_DOWNLOAD_REQUEST:
      return TrackDownloadRequest(**self.data)


# region Server
class WebsocketServerMessageType(Enum):
  SERVER_MESSAGE_TYPES = 0

  TRACK_INFO = 1
  
  # You searched: "{query}", ticket: {ticket}
  SEARCH_RESPONSE = 2

  # Downloading {filename} from {username}...
  TRACK_DOWNLOAD_RESPONSE = 3


class SearchResponse(BaseModel):
  query: str
  ticket: int
  total_results: int = 0
  current_results: int = 0
  resultset: set[TrackInfo]|None = None


class TrackDownloadStatus(Enum):
  PENDING = 1
  COMPLETED = 2
  FAILED = 3


class TrackDownloadInfo(BaseModel):
  ticket: int
  username: str
  filename: str
  status: TrackDownloadStatus = TrackDownloadStatus.PENDING


class WebsocketServerMessage(BaseModel):
  msg_type: WebsocketServerMessageType
  data: Any

  @staticmethod
  def from_ws_server_message_enum() -> 'WebsocketServerMessage':
    return WebsocketServerMessage (
      msg_type= WebsocketServerMessageType.SERVER_MESSAGE_TYPES,
      data= { i.name: i.value for i in WebsocketServerMessageType }
      )

  @staticmethod
  def from_search_response( query: str, 
                            ticket: int,
                            total_results: int,
                            resultset: Iterable[TrackInfo]|None = None) -> 'WebsocketServerMessage':
    current_results = len(resultset) if resultset else 0

    return WebsocketServerMessage(
      msg_type= WebsocketServerMessageType.SEARCH_RESPONSE,
      data= SearchResponse(
          query= query,
          ticket= ticket,
          resultset= resultset,
          total_results= total_results,
          current_results= current_results
        )
    )

  @staticmethod
  def from_track_info_list(track_info_list: list[TrackInfo]) -> 'WebsocketServerMessage':
    return WebsocketServerMessage(
      msg_type= WebsocketServerMessageType.TRACK_INFO,
      data= track_info_list
    )

  @staticmethod
  def from_track_download_response( ticket: int, 
                                    username: str, 
                                    filename: str,
                                    status: TrackDownloadStatus) -> 'WebsocketServerMessage':
    return WebsocketServerMessage(
      msg_type= WebsocketServerMessageType.TRACK_DOWNLOAD_RESPONSE,
      data= TrackDownloadInfo(
          ticket= ticket,
          username= username,
          filename= filename,
          status= status
        )
    )