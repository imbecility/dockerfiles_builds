import os
from browserforge.fingerprints import Screen
from camoufox.server import launch_server

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7861"))
    ws_path = os.getenv("WS_PATH", "camoufox")

    server_kwargs = {
        "host": "0.0.0.0",
        "port": port,
        "ws_path": ws_path,
        "headless": False,
        "os": ["windows", "macos"],
        "screen": Screen(max_width=1920, max_height=1080),
        "humanize": 1.5,
        "geoip": False,
        "disable_coop": True,
        "allow_webgl": True,
        "enable_cache": True,
        "i_know_what_im_doing": True,
        "config": {
            "forceScopeAccess": True
        },
        "firefox_user_prefs": {
            "network.trr.mode": 5,
            "network.dns.disableIPv6": True,
        },
        "env": {
            # песочница Firefox (в т.ч. изоляция сетевого Socket Process) может
            # опираться на ptrace/seccomp-механизмы, которые уже заняты сенсором
            # SlimToolkit во время динамического анализа — пробуем полностью
            # отключить эту песочницу как диагностический шаг
            "MOZ_DISABLE_CONTENT_SANDBOX": "1",
        },
    }


    proxy_url = os.getenv("PROXY_SERVER")
    if proxy_url:
        server_kwargs["proxy"] = {
            "server": proxy_url,
            "username": os.getenv("PROXY_USER", ""),
            "password": os.getenv("PROXY_PASS", "")
        }

    launch_server(**server_kwargs)