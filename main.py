import asyncio
import os
from datetime import datetime
import uvicorn
import multiprocessing
import sys
from web_app import app as web_app
from database import db
from wasabi_storage import storage
from dotenv import load_dotenv

load_dotenv()

def run_bot_process():
    """Run the Telegram bot as a separate process"""
    try:
        print("🤖 Starting Telegram File Bot...")
        log_file = open("bot.log", "a")
        # Use sys.executable to ensure correct Python environment
        subprocess_args = [sys.executable, "simple_bot.py"]
        import subprocess
        process = subprocess.Popen(
            subprocess_args,
            stdout=log_file,
            stderr=log_file,
            bufsize=1
        )
        print("🚀 Telegram File Bot started! Logs: bot.log")
        process.wait()  # Wait for bot to exit
    except Exception as e:
        print(f"❌ Bot startup error: {e}")

async def main():
    """Main async entry point"""
    print("🚀 Starting Telegram File Bot services...")

    # Initialize database
    await db.connect()
    print("✅ Database connected")

    # Test Wasabi connection
    if await storage.test_connection():
        print("✅ Wasabi storage connected")
    else:
        print("⚠️ Wasabi storage connection failed")

    # Start bot in separate process
    bot_process = multiprocessing.Process(target=run_bot_process, daemon=True)
    bot_process.start()

    # Start Uvicorn web server
    port = int(os.getenv("PORT", 5000))
    config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        # Terminate bot if web server stops
        if bot_process.is_alive():
            print("🛑 Stopping Telegram bot...")
            bot_process.terminate()
            bot_process.join()

def run_main():
    print("=" * 50)
    print("🚀 TELEGRAM FILE BOT")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check environment variables
    required_vars = [
        'API_ID', 'API_HASH', 'BOT_TOKEN',
        'WASABI_ACCESS_KEY', 'WASABI_SECRET_KEY', 'WASABI_BUCKET',
        'DATABASE_URL'
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        return

    # Run main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
    except Exception as e:
        print(f"❌ Application error: {e}")

if __name__ == "__main__":
    run_main()
        
