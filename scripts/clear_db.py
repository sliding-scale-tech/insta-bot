import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(".env"), override=True)
load_dotenv(Path(".env.local"), override=True)
from convex import ConvexClient
client = ConvexClient(os.environ["CONVEX_URL"])
result = client.mutation("bot:clearAll", {})
print(f"Cleared {result['deleted']} records from Convex cloud")
