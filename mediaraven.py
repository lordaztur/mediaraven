import sys

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters

from config import (
    LOCAL_API_URL,
    LOCAL_FILE_URL,
    TOKEN,
    setup_logging,
    validate_runtime_config,
)
from handlers import (
    caption_callback,
    download_confirm_callback,
    handle_message,
    lang_callback,
    retry_callback,
    screenshot_callback,
)
from lifecycle import init_deno, init_ffmpeg, init_globals, stop_globals
from messages import msg


if __name__ == '__main__':
    setup_logging()

    if not TOKEN:
        print(msg("startup.token_missing"))
        sys.exit(1)

    config_errors = validate_runtime_config()
    if config_errors:
        for err in config_errors:
            print(f"❌ Config inválida: {err}")
        sys.exit(1)

    init_deno()
    init_ffmpeg()

    print(msg("startup.connecting", api_url=LOCAL_API_URL))

    builder = ApplicationBuilder().token(TOKEN)
    builder.base_url(LOCAL_API_URL)
    builder.base_file_url(LOCAL_FILE_URL)
    builder.local_mode(True)
    builder.post_init(init_globals)
    builder.post_shutdown(stop_globals)
    application = builder.concurrent_updates(True).build()
    application.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(retry_callback, pattern=r"^retry_"))
    application.add_handler(CallbackQueryHandler(lang_callback, pattern=r"^lang\|"))
    application.add_handler(CallbackQueryHandler(caption_callback, pattern=r"^cap\|"))
    application.add_handler(CallbackQueryHandler(screenshot_callback, pattern=r"^scrn\|"))
    application.add_handler(CallbackQueryHandler(download_confirm_callback, pattern=r"^dl\|"))

    print(msg("startup.ready"))
    application.run_polling()
