import sys
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright._impl._api_structures import SetCookieParam  # noqa
from playwright.sync_api import BrowserContext, sync_playwright

from shared import run_chromium_smoke_suite, run_main, wait_for_cdp_server

CDP_URL = "http://localhost:7860"

COOKIES: list[SetCookieParam] = [
    {'name': 'ys', 'value': 'wprid.1779106375637420-12880543316618692126-balancer-l7leveler-kubr-yp-klg-290-BAL', 'domain': '.yandex.com', 'path': '/', 'httpOnly': False, 'secure': True, 'sameSite': 'None', 'expires': 2094715208.043561},
    {'name': 'yp', 'value': '1779970352.dlp.2#2094466377.pcs.1#1810642356.sp.shst%3A1%3Ashsh%3A1%3Afamily%3A0#1779711159.szm.1_25%3A2048x1152%3A2033x1031%3A15#1779279175.ygo.10493%3A87#1781698375.ygu.0', 'domain': '.yandex.com',
     'path': '/', 'httpOnly': False, 'secure': True, 'sameSite': 'None', 'expires': 2094715208.088647},
    {'name': 'yandex_gid', 'value': '87', 'domain': '.yandex.com', 'path': '/', 'httpOnly': False, 'secure': True, 'sameSite': 'None', 'expires': 2094715208.433255},
]


def run_yandex_search_scenario(context: BrowserContext, query: str) -> None:
    context.add_cookies(COOKIES)
    page = context.new_page()
    try:
        page.goto('chrome://extensions/', wait_until='domcontentloaded', timeout=60000)
        page.screenshot(path='extensions.jpeg', full_page=False, type='jpeg', quality=50)

        page.goto(
            f'https://yandex.com/search?text={quote(query.replace(" ", "+"), safe="+")}&lr=84',
            wait_until='domcontentloaded',
            timeout=90000,
        )

        page.add_style_tag(content='''
                .plus-link,
                .plus-link_inactive,
                .plus-link__content,
                .plus-link__icon,
                .plus-link__text,
                .Distribution,
                .DistributionPopup,
                .DistributionInfo,
                [id^="DistributionPopupDesktopSystemNarrow"],
                [data-fast-name="images"],
                [data-fast-name="video-unisearch"]{
                    display: none !important;
                    width: 0px !important;
                    height: 0px !important;
                    position: absolute !important;
                    left: -999999px !important;
                    z-index: -999999 !important;
                }
                ''')
        try:
            footer_link = page.wait_for_selector('.SerpFooter-LinksGroup_type_settings', timeout=20000)
            footer_link.scroll_into_view_if_needed()
            footer_link.click(force=True)
        except Exception as e:
            print(e)

        print(f'итоговый URL: "{page.url}"')
        page.screenshot(path='screen.jpeg', full_page=True, type='jpeg', quality=50)

        with open('page.html', 'w+', encoding='utf-8') as f:
            f.write(page.content())
    finally:
        page.close()


def main(query: str = 'bufo bufo care', seed: str = 'yandex_search') -> None:
    wait_for_cdp_server(CDP_URL, timeout=30)

    params = urlencode({'fingerprint': seed, 'geoip': 'true'}, safe=':/@-_')
    endpoint = f'{CDP_URL.rstrip("/")}?{params}'

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(endpoint)
        context = browser.contexts[0]

        context.set_default_timeout(10000)
        run_chromium_smoke_suite(context, expected_extensions_count=7)

        context.set_default_timeout(60000)
        run_yandex_search_scenario(context, query)

        context.close()
        browser.close()


if __name__ == "__main__":
    run_main(main)