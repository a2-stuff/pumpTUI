import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient


async def test_connection():
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    print(f"Connecting to {uri}...")
    
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
        await client.admin.command('ping')
        print("✅ Connection Successful!")
        
        db = client["pumptui"]
        # Test Write
        res = await db["test_conn"].insert_one({"status": "ok", "ts": 123})
        print(f"✅ Write Successful! ID: {res.inserted_id}")
        
        # Test Read
        doc = await db["test_conn"].find_one({"_id": res.inserted_id})
        if doc:
            print(f"✅ Read Successful! Doc: {doc}")
        else:
            print("❌ Read Failed!")
            
        # Clean up
        await db["test_conn"].delete_one({"_id": res.inserted_id})
        print("✅ Clean up Successful!")
        
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
