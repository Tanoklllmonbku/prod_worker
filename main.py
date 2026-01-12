"""
Main entry point for LLM Service

This script initializes and starts the LLM worker service with multi-worker load distribution.
For K8s deployment, configure environment variables or .env file.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.service import LLMService

async def main():
    """Main entry point"""
    service = LLMService()

    try:
        await service.start()
    except Exception as e:
        if service.logger:
            service.logger.critical("Fatal error: %s", e, exc_info=True)
        else:
            print(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
