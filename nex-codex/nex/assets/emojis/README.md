# NEX CODEX bundled emoji artwork

All 49 static 128×128 PNGs are included in the complete project ZIP: 48 supplied icons plus nex_previous mirrored from nex_next. Original dark tiles/cyan glow preserved with transparent outer corners. Images are below 256 KiB; runtime needs no Pillow.

Start python main.py with a valid bot token. AUTO_LOAD_EMOJIS=true is the default. The bot fetches application-owned emojis, uploads missing nex_* artwork, and uses the real returned IDs in its 14 theme slots before loading cogs/persistent views. All 49 assets are uploaded, including additional artwork not currently assigned to a slot. Existing uploads persist at Discord and are reused across restarts/hosts with the same application token. No manual upload, emoji IDs or command is required. Application-owned emojis do not need server emoji permissions or slots.

Progress/failures appear in the hosting console. Missing files/API denial/capacity/timeouts leave working Unicode fallbacks; successful partial uploads are reused after restart. Automatic loading is bounded to 180 seconds. Keep this entire folder when uploading the project to Wispbyte.

Server emojis overrides take priority. /configure key:emojis value:{} restores automatic defaults. The optional /installemojis command creates 14 server-owned overrides and still requires server Create/Manage Expressions permission and capacity. Repost existing panels to refresh stored button artwork. No live Discord upload is claimed by offline tests.
