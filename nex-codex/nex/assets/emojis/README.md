# NEX CODEX supplied emoji artwork

49 static 128×128 PNGs cropped from the artwork supplied by the user:48 source icons plus nex_previous mirrored from nex_next. Original dark tiles and cyan glow preserved; outer corners are transparent. All are below Discord's 256 KiB upload bound. Source processing used Pillow only as a build tool; runtime needs no Pillow.

Use /installemojis as a configured owner or server administrator. The bot needs Create Expressions or Manage Expressions. Up to 14 free static emoji slots are needed. The installer uses the mapping in nex/services/emojis.py and saves only IDs returned by Discord. It reuses available unrestricted static nex_* emojis. Successful partial batches remain saved; retry to complete. No uploads are claimed until the real command runs successfully.

The remaining artwork can be uploaded manually through Discord. Custom theme overrides use /configure key:emojis value:{"shop":"<:nex_cart:YOUR_REAL_ID>"}. Replace the ID with a real Discord emoji ID. Repost shop panels to refresh old buttons.
