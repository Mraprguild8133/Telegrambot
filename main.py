import asyncio
import os
from datetime import datetime
import uvicorn
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from web_app import app as web_app
from database import db
from wasabi_storage import storage

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def run_bot_process():
    """Run the bot in a separate process"""
    try:
        print("🤖 Starting Telegram bot...")
        import subprocess
        # Start bot in background without waiting
        subprocess.Popen(['python', 'simple_bot.py'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        print("🚀 Telegram File Bot started!")
    except Exception as e:
        print(f"❌ Bot startup error: {e}")

async def main():
    """Main function to start all services"""
    print("🚀 Starting Telegram File Bot services...")
    
    # Initialize database
    await db.connect()
    print("✅ Database connected")
    
    # Test Wasabi connection
    if await storage.test_connection():
        print("✅ Wasabi storage connected")
    else:
        print("⚠️ Wasabi storage connection failed - check credentials")
    
    # Start bot in separate process
    bot_process = multiprocessing.Process(target=run_bot_process, daemon=True)
    bot_process.start()
    
    print("🌐 Starting web server...")
    config = uvicorn.Config(
        web_app, 
        host="0.0.0.0", 
        port=5000,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    await server.serve()

def run_main():
    """Main entry point"""
    print("=" * 50)
    print("🚀 TELEGRAM FILE BOT")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check required environment variables
    required_vars = [
        'API_ID', 'API_HASH', 'BOT_TOKEN',
        'WASABI_ACCESS_KEY', 'WASABI_SECRET_KEY', 'WASABI_BUCKET',
        'DATABASE_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables and restart the application.")
        return
    
    # Start the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
    except Exception as e:
        print(f"❌ Application error: {e}")

if __name__ == "__main__":
    run_main()