class WebSocketClient {
  static Events = {
    OPEN: 'open',
    MESSAGE: 'message',
    CLOSE: 'close',
    ERROR: 'error'
  };
  
  constructor(url) {
    this.url = url;
    this.websocket = null;
    this.eventHandlers = {};
  }
  
  connect() {
    this.websocket = new WebSocket(this.url);
    
    this.websocket.onopen = () => {
      this._triggerEvent(WebSocketClient.Events.OPEN);
    };
    
    this.websocket.onmessage = (event) => {
      this._triggerEvent(WebSocketClient.Events.MESSAGE, event);
    };
    
    this.websocket.onclose = () => {
      this._triggerEvent(WebSocketClient.Events.CLOSE);
    };
    
    this.websocket.onerror = (error) => {
      this._triggerEvent(WebSocketClient.Events.ERROR, error);
    };
  }
  
  sendMessage(message) {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify(message));
    } else {
      throw new Error('WebSocket is not open');
    }
  }
  
  close() {
    if (this.websocket) {
      this.websocket.close();
    }
  }
  
  on(event, handler) {
    if (!Array.from(Object.values(WebSocketClient.Events)).includes(event)) {
      throw new Error(`Unknown event: ${event}`);
    }

    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = [];
    }
    this.eventHandlers[event].push(handler);
  }
  
  _triggerEvent(event, data) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event].forEach((handler) => handler(data));
    }
  }
}


class TrackInfo {
  /**
  * 
  * @param {string} Id
  * @param {int} ticket 
  * @param {string} username 
  * @param {string} filename 
  * @param {string} fullpath 
  * @param {string} extension 
  * @param {int} filesize 
  * @param {object} attributes 
  * @param {int} bitrate 
  * @param {int} sample_rate 
  * @param {int} bit_depth 
  * @param {int} duration 
  */
  constructor(Id, ticket, username, filename, fullpath, extension, filesize, attributes, bitrate, sample_rate, bit_depth, duration) {
    this.Id = Id;
    this.ticket = ticket;
    this.username = username;
    this.filename = filename;
    this.fullpath = fullpath;
    this.extension = extension;
    this.filesize = filesize;
    this.attributes = attributes;
    this.bitrate = bitrate;
    this.sample_rate = sample_rate;
    this.bit_depth = bit_depth;
    this.duration = duration;
  }

  static fromJson(d) {
    return new TrackInfo(
      d.Id,
      d.ticket,
      d.username,
      d.filename,
      d.fullpath,
      d.extension,
      d.filesize,
      d.attributes,
      d.bitrate,
      d.sample_rate,
      d.bit_depth,
      d.duration
    );
  }
}


class SearchResponse {
  /**
  * 
  * @param {string} Id 
  * @param {string} query 
  * @param {int} ticket 
  * @param {int} total_results 
  * @param {int} current_results 
  * @param {Array<TrackInfo>} resultset
  */
  constructor(Id, query, ticket, total_results, current_results, resultset) {
    this.Id = Id;
    this.query = query;
    this.ticket = ticket;
    this.total_results = total_results;
    this.current_results = current_results;
    this.resultset = resultset;
  }

  static fromJson(d) {
    return new SearchResponse(
      d.Id,
      d.query,
      d.ticket,
      d.total_results,
      d.current_results,
      d.resultset.map((trackInfo) => TrackInfo.fromJson(trackInfo))
    );
  }
}


class TrackDownloadInfo {
  /**
  * 
  * @param {int} ticket 
  * @param {string} username 
  * @param {string} filename 
  * @param {string} status 
  */
  constructor(ticket, username, filename, status) {
    this.ticket = ticket;
    this.username = username;
    this.filename = filename;
    this.status = status;
  }

  static fromJson(d) {
    return new TrackDownloadInfo(
      d.ticket,
      d.username,
      d.filename,
      d.status
    );
  }
}

class WsError {
  /**
  * 
  * @param {int} code 
  * @param {string} msg 
  * @param {bool} fatal 
  */
  constructor(code, msg, fatal) {
    this.code = code;
    this.msg = msg;
    this.fatal = fatal;
  }

  static fromJson(d) {
    return new WsError(
      d.code,
      d.msg,
      d.fatal
    );
  }
}


class SlskWebSocketClient {
  constructor(url) {
    this.websocketClient = new WebSocketClient(url);

    this.websocketClient.on(WebSocketClient.Events.MESSAGE, this._onMessage.bind(this));

    this.eventHandlers = {
      searchResponse: [],
      trackInfo: [],
      trackDownloadResponse: [],
      slskError: []
    };
  }
  
  static ClientMessageTypes = {
    SEARCH_REQUEST: 1,
    TRACK_DOWNLOAD_REQUEST: 2
  };
  
  static ServerMessageTypes = {
    SERVER_MESSAGE_TYPES: 0,
    TRACK_INFO: 1,
    SEARCH_RESPONSE: 2,
    TRACK_DOWNLOAD_RESPONSE: 3,  
    ERROR: 4
  };
  
  connect() {
    this.websocketClient.connect();
  }

  close() {
    this.websocketClient.close();
  }

  /**
  * 
  * @param {string} query 
  */
  sendSearchRequest(query) {
    const message = {
      msg_type: SlskWebSocketClient.ClientMessageTypes.SEARCH_REQUEST,
      data: { query }
    };
    this.websocketClient.sendMessage(message);
  }
  
  /**
  * 
  * @param {int} ticket 
  * @param {string} username 
  * @param {string} filename 
  */
  sendTrackDownloadRequest(ticket, username, filename) {
    const message = {
      msg_type: SlskWebSocketClient.ClientMessageTypes.TRACK_DOWNLOAD_REQUEST,
      data: { ticket, username, filename }
    };
    this.websocketClient.sendMessage(message);
  }
  
  /**
  * 
  * @param {MessageEvent} event 
  */
  _onMessage(event) {
    const s = event.data;

    const data = JSON.parse(s);

    try {
      if (data.msg_type === SlskWebSocketClient.ServerMessageTypes.SEARCH_RESPONSE) {
        const searchResponse = SearchResponse.fromJson(data.data);
        
        this._triggerEvent('searchResponse', searchResponse);
      }

      else if (data.msg_type === SlskWebSocketClient.ServerMessageTypes.TRACK_INFO) {
        const trackInfo = TrackInfo.fromJson(data.data);
        
        this._triggerEvent('trackInfo', trackInfo);
      }

      else if (data.msg_type === SlskWebSocketClient.ServerMessageTypes.TRACK_DOWNLOAD_RESPONSE) {
        const trackDownloadInfo = TrackDownloadInfo.fromJson(data.data);

        this._triggerEvent('trackDownloadResponse', trackDownloadInfo);
      }

      else if (data.msg_type === SlskWebSocketClient.ServerMessageTypes.ERROR) {
        const wserror = WsError.fromJson(data.data);

        this._triggerEvent('slskError', wserror);
      }
    }

    catch (e) {
      console.error(e);
    }
  }
  
  on (event, handler) {
    if (!Array.from(Object.keys(this.eventHandlers)).includes(event)) {
      throw new Error(`Unknown event: ${event}`);
    }

    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = [];
    }

    this.eventHandlers[event].push(handler);
  }

  onSearchResponse(handler) {
    this.on('searchResponse', handler);
  }

  onTrackInfo(handler) {
    this.on('trackInfo', handler);
  }

  onTrackDownloadResponse(handler) {
    this.on('trackDownloadResponse', handler);
  }

  onError(handler) {
    this.on('slskError', handler);
  }

  _triggerEvent(event, data) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event].forEach((handler) => handler(data));
    }
  }
}