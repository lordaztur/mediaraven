import logging
import os
import shutil
import sqlite3
import tempfile
from urllib.parse import urlparse

import state
from config import FIREFOX_PROFILE_PATH
from messages import lmsg

logger = logging.getLogger(__name__)


def extract_firefox_cookies() -> list[dict]:
    db_path = os.path.join(FIREFOX_PROFILE_PATH, 'cookies.sqlite')
    if not os.path.exists(db_path):
        logger.warning(lmsg("cookies.banco_de_cookies", db_path=db_path))
        return []

    fd, temp_db = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    shutil.copy2(db_path, temp_db)

    cookies = []
    MAX_PLAYWRIGHT_EXPIRY = 253402300799

    try:
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name, value, host, path, expiry, isSecure, isHttpOnly FROM moz_cookies")

        for row in cursor.fetchall():
            name, value, host, path, expiry, isSecure, isHttpOnly = row

            clean_expires = -1
            if expiry is not None:
                try:
                    val = int(float(expiry))
                    if val > MAX_PLAYWRIGHT_EXPIRY:
                        clean_expires = MAX_PLAYWRIGHT_EXPIRY
                    elif val > 0:
                        clean_expires = val
                except (ValueError, TypeError):
                    pass

            cookies.append({
                'name': name,
                'value': value,
                'domain': host,
                'path': path,
                'expires': clean_expires,
                'secure': bool(isSecure),
                'httpOnly': bool(isHttpOnly)
            })
        conn.close()
    except Exception as e:
        logger.error(lmsg("cookies.erro_ao_ler", e=e), exc_info=True)
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)

    return cookies


def get_aiohttp_cookies_for_url(url: str) -> dict[str, str]:
    domain = urlparse(url).netloc.lower()
    return {c['name']: c['value'] for c in state.FIREFOX_COOKIES_CACHE if c['domain'].lstrip('.').lower() in domain}
