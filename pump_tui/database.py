import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet
from .config import config

# Setup logging
logging.basicConfig(filename="db_error.log", level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s:%(message)s')

class Database:
    """Async MongoDB Wrapper for PumpTUI with Robust Error Handling & Encryption."""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.tokens = None
        self.settings = None
        self.wallets = None
        self.connected = False
        
        # Encryption
        self._cipher = None
        
    def _get_cipher(self):
        if not self._cipher:
            key = os.getenv("SETTINGS_ENCRYPTION_KEY")
            if key:
                try:
                    self._cipher = Fernet(key.encode())
                except Exception as e:
                    logging.error(f"Invalid Encryption Key: {e}")
        return self._cipher

    async def connect(self, retries: int = 5, initial_delay: float = 1.0):
        """Initialize connection to MongoDB with retry logic.
        
        Args:
            retries: Number of connection attempts (default 5)
            initial_delay: Initial delay between retries in seconds (doubles each retry)
        """
        if self.connected: 
            return True

        delay = initial_delay
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27018")
        
        for attempt in range(1, retries + 1):
            try:
                self.client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
                
                # Verify connection (fails fast)
                await self.client.admin.command('ping')
                
                self.db = self.client["pumptui"]
                self.tokens = self.db["tokens"]
                self.settings = self.db["settings"]
                self.wallets = self.db["wallets"]
                
                # Create indexes
                await self.tokens.create_index("mint", unique=True)
                await self.tokens.create_index([("volume_buckets", 1)])
                await self.tokens.create_index("last_updated")
                await self.settings.create_index("key", unique=True)
                
                self.connected = True
                logging.info(f"MongoDB Connected on attempt {attempt}")
                return True
                
            except Exception as e:
                logging.warning(f"MongoDB Connection Attempt {attempt}/{retries} Failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logging.error(f"MongoDB Connection Failed after {retries} attempts: {e}")
                    self.connected = False
                    return False
        
        return False

    async def reconnect(self):
        """Attempt to reconnect to MongoDB if not connected."""
        if self.connected:
            return True
        
        # Close any existing client
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        
        return await self.connect(retries=3, initial_delay=2.0)

    async def close(self):
        if self.client:
            self.client.close()
            self.connected = False

    async def update_token_event(self, event: Dict[str, Any]):
        """Fire-and-forget update of token data."""
        if not self.connected or not event.get("mint"):
            return

        try:
            mint = event.get("mint")
            now = datetime.now()
            
            update_ops = {}
            inc_ops = {}
            set_ops = {}
            
            # Bucket Key: "2023-10-27T10"
            bucket_key = f"volume_buckets.{now.strftime('%Y-%m-%dT%H')}"
            
            sol_amt = float(event.get("solAmount") or 0)
            
            # Bonk pool estimation logic
            if sol_amt == 0 and event.get("pool") == "bonk" and "marketCapSol" in event and "tokenAmount" in event:
                 try:
                     token_amt = float(event.get("tokenAmount") or 0)
                     mc_sol = float(event.get("marketCapSol") or 0)
                     price_sol = mc_sol / 1_000_000_000
                     sol_amt = token_amt * price_sol
                 except: pass

            if sol_amt > 0:
                inc_ops[bucket_key] = sol_amt
                inc_ops["volume_total"] = sol_amt

            if "name" in event: set_ops["name"] = event["name"]
            if "symbol" in event: set_ops["symbol"] = event["symbol"]
            if "marketCapSol" in event: set_ops["marketCapSol"] = float(event["marketCapSol"])
            if "pool" in event: set_ops["pool"] = event["pool"]
            
            if event.get("txType") == "create":
                set_ops["creator"] = event.get("traderPublicKey")

            if "txType" in event:
                if event["txType"] == "buy": inc_ops["buys_count"] = 1
                elif event["txType"] == "sell": inc_ops["sells_count"] = 1
            
            inc_ops["tx_count"] = 1
            set_ops["last_updated"] = now
            
            if "traderPublicKey" in event:
                update_ops["$addToSet"] = {"traders": event["traderPublicKey"]}
            
            update_ops["$set"] = set_ops
            if inc_ops:
                update_ops["$inc"] = inc_ops
                
            await self.tokens.update_one({"mint": mint}, update_ops, upsert=True)
        except Exception as e:
            logging.error(f"Token Update Error: {e}")

    async def get_recent_tokens(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Fetch recent tokens for initial load."""
        if not self.connected: return []
        try:
            cursor = self.tokens.find().sort("last_updated", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logging.error(f"Get Recent Error: {e}")
            return []

    async def get_runners(self, limit: int = 50, sort_by: str = "volume", sort_dir: int = -1) -> List[Dict[str, Any]]:
        """
        Query top tokens (Runners) in the last 12h.
        sort_by: "volume" or "market_cap"
        """
        if not self.connected: return []

        now = datetime.now()
        # 12 Hour Window
        bucket_keys = []
        for i in range(12):
            t = now - timedelta(hours=i)
            key = f"$volume_buckets.{t.strftime('%Y-%m-%dT%H')}"
            bucket_keys.append(key)

        pipeline = [
            {
                "$match": {
                    "last_updated": {"$gte": now - timedelta(hours=12)}
                }
            },
            {
                "$addFields": {
                    "volume_12h": {
                        "$sum": bucket_keys
                    }
                }
            }
        ]
        
        # Sort logic
        sort_field = "volume_12h"
        if sort_by == "market_cap":
            sort_field = "marketCapSol"
        
        pipeline.append({"$sort": {sort_field: sort_dir}})
        pipeline.append({"$limit": limit})

        try:
            cursor = self.tokens.aggregate(pipeline)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logging.error(f"Get Runners Error: {e}")
            return []

    async def get_creator_stats(self, creator_pubkey: str) -> Dict[str, int]:
        """Fetch launch and migration counts for a creator."""
        if not self.connected: return {"launched": 0, "migrated": 0}
        try:
            # Count tokens launched by this wallet
            launched = await self.tokens.count_documents({"creator": creator_pubkey})
            # Count migrated tokens (pool == "bonk" indicator)
            migrated = await self.tokens.count_documents({"creator": creator_pubkey, "pool": "bonk"})
            return {"launched": launched, "migrated": migrated}
        except Exception as e:
            logging.error(f"Get Creator Stats Error: {e}")
            return {"launched": 0, "migrated": 0}

    # --- Settings & Wallets ---

    async def save_setting(self, key: str, value: Any, encrypt: bool = False):
        """Save a setting, optionally encrypting string values."""
        if not self.connected: return
        try:
            stored_val = value
            if encrypt and isinstance(value, str):
                cipher = self._get_cipher()
                if cipher:
                    stored_val = cipher.encrypt(value.encode()).decode()
            
            await self.settings.update_one(
                {"key": key},
                {"$set": {"value": stored_val, "encrypted": encrypt}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Save Setting Error: {e}")

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting, decrypting if necessary."""
        if not self.connected: return default
        try:
            doc = await self.settings.find_one({"key": key})
            if not doc: return default
            
            val = doc.get("value")
            if doc.get("encrypted"):
                cipher = self._get_cipher()
                if cipher and isinstance(val, str):
                    try:
                        return cipher.decrypt(val.encode()).decode()
                    except:
                        return default # Decryption failed
            return val
        except Exception as e:
            logging.error(f"Get Setting Error: {e}")
            return default

    async def save_wallet(self, label: str, private_key: str, public_key: str):
        """Save a wallet securely."""
        if not self.connected: return
        try:
            # Encrypt private key
            enc_pk = private_key
            cipher = self._get_cipher()
            if cipher:
                enc_pk = cipher.encrypt(private_key.encode()).decode()
            
            wallet_data = {
                "label": label,
                "privateKey": enc_pk, # Encrypted
                "walletPublicKey": public_key,
                "created_at": datetime.now()
            }
            # Assuming label is unique or we use pubkey as ID? 
            # Let's use pubkey as unique ID
            await self.wallets.update_one(
                {"walletPublicKey": public_key},
                {"$set": wallet_data},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Save Wallet Error: {e}")

    async def get_wallets(self) -> List[Dict[str, str]]:
        """Get all wallets, decrypting private keys."""
        if not self.connected: return []
        try:
            cursor = self.wallets.find({})
            wallets = []
            cipher = self._get_cipher()
            
            async for doc in cursor:
                # Decrypt
                pk = doc.get("privateKey")
                if cipher and pk:
                    try:
                        pk = cipher.decrypt(pk.encode()).decode()
                    except:
                        pk = None # corrupt or wrong key
                
                wallets.append({
                    "label": doc.get("label", "Unknown"),
                    "privateKey": pk,
                    "walletPublicKey": doc.get("walletPublicKey")
                })
            return wallets
        except Exception as e:
            logging.error(f"Get Wallets Error: {e}")
            return []

db = Database()
