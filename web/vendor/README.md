# MediaMTX browser reader

`mediamtx-reader.js` is unmodified upstream MediaMTX **v1.21.1**, matching the installed Pi server.

Source: https://github.com/bluenviron/mediamtx/blob/v1.21.1/internal/servers/webrtc/reader.js

SHA-256: `a802f229b803c33713d4c69c4cc0d480108a5bf384947aeee4aaf04268bf85c1`

MIT license is reproduced in `mediamtx-LICENSE`. Updates require rechecking the `onTrack` receiver and cleanup behavior. The Ascent wrapper uses the public track event's receiver; no private peer-connection access or runtime monkeypatching.
