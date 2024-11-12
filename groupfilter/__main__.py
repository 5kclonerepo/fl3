import uvloop
from pyrogram import Client, idle, __version__
from pyrogram.raw.all import layer
from groupfilter import APP_ID, API_HASH, BOT_TOKEN

uvloop.install()


app = None


async def main():
    global app
    plugins = dict(root="groupfilter/plugins")
    app = Client(
        name="groupfilter",
        api_id=APP_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins,
    )
    async with app:
        me = await app.get_me()
        print(
            f"{me.first_name} - @{me.username} - Pyrogram v{__version__} (Layer {layer}) - Started..."
        )
        await idle()
        print(f"{me.first_name} - @{me.username} - Stopped !!!")


uvloop.run(main())
