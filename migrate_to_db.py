import asyncio
import os
import json
from pump_tui.database import db

async def migrate():
    print("Starting Migration...")
    
    # Connect
    await db.connect()
    if not db.connected:
        print("❌ DB Connection Failed. Make sure MongoDB is running.")
        return

    # 1. Migrate .env Settings
    print("Migrating .env settings...")
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    
                    # Specific Keys to migrate
                    if key in ["RPC_URL", "API_KEY", "DEFAULT_SLIPPAGE", "DEFAULT_PRIORITY_FEE"]:
                        print(f"  Saving {key}...")
                        encrypt = False
                        if key == "API_KEY": encrypt = True # Encrypt API Key? User only asked for env migration, usually API keys are secret.
                        await db.save_setting(key.lower(), val, encrypt=encrypt)
    
    # 2. Migrate wallets.json
    print("Migrating wallets.json...")
    wallets_file = "wallets.json"
    if os.path.exists(wallets_file):
        try:
            with open(wallets_file, "r") as f:
                wallets = json.load(f)
                
            for w in wallets:
                pub = w.get("walletPublicKey")
                pk = w.get("privateKey")
                label = w.get("label", "Migrated Wallet")
                active = w.get("active", False)
                
                if pub and pk:
                    print(f"  Saving Wallet {pub[:6]}...")
                    # Save wallet (encrypts PK)
                    await db.save_wallet(label, pk, pub)
                    
                    # Store active status
                    if active:
                         await db.settings.update_one(
                             {"key": "active_wallet"},
                             {"$set": {"value": pub}},
                             upsert=True
                         )
        except Exception as e:
            print(f"  ❌ Error reading wallets.json: {e}")
            
    print("✅ Migration Complete.")
    await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
