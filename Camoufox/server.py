import os
from camoufox.server import launch_server
from browserforge.fingerprints import Screen

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7861"))
    ws_path = os.getenv("WS_PATH", "camoufox")

    proxy_url = os.getenv("PROXY_SERVER")
    proxy_config = {
            "server": proxy_url,
            "username": os.getenv("PROXY_USER", ""),
            "password": os.getenv("PROXY_PASS", "")
        } if proxy_url else None

    launch_server(
        host="0.0.0.0",
        port=port,
        ws_path=ws_path,
        headless=False,
        geoip=True,
        proxy=proxy_config,
        os=["windows", "macos"],
        screen=Screen(max_width=1920, max_height=1080),
        humanize=1.5,
        disable_coop=True,
        allow_webgl=True,
        enable_cache=True,
        i_know_what_im_doing=True,
        firefox_user_prefs={
            "security.sandbox.content.level": 0,
            "security.sandbox.socket.process.level": 0,
        },
        config={
            "forceScopeAccess": True
        }
    )
