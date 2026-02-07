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

# Import using the improved import system
from services.service import LLMService  # Import to trigger registration
from core.service_manager import initialize_service_manager, get_service_manager
from core.service_factory import create_service
from config.config import get_settings

async def main():
    """Main entry point"""
    config = get_settings()

    # Initialize service manager
    service_manager = initialize_service_manager(config)

    # Add LLM service to the manager
    success = service_manager.add_service_by_type('llm_service', 'llm', config=config)

    if not success:
        print("Failed to create service 'llm'")
        sys.exit(1)

    try:
        await service_manager.start_all()
    except KeyboardInterrupt:
        print("Received interrupt signal, shutting down...")
    except Exception as e:
        service = service_manager.get_service('llm_service')
        if service and hasattr(service, '_logger') and service._logger:
            service._logger.critical("Fatal error: %s", e, exc_info=True)
        else:
            print(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            await service_manager.stop_all()
        except Exception as e:
            print(f"Error during shutdown: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    