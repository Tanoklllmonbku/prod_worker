"""
Module for managing registries of connectors and interfaces.
Provides decorators for easy registration of new implementations.
"""

from typing import Dict, Type, Any
from functools import wraps

# Global registries
CONNECTOR_REGISTRY: Dict[str, Type[Any]] = {}
INTERFACE_REGISTRY: Dict[str, Type[Any]] = {}


def register_connector(name: str):
    """
    Decorator to register a connector class in the global registry.
    
    Args:
        name: The name to register the connector class under
    """
    def decorator(cls):
        CONNECTOR_REGISTRY[name] = cls
        return cls
    return decorator


def register_interface(name: str):
    """
    Decorator to register an interface class in the global registry.
    
    Args:
        name: The name to register the interface class under
    """
    def decorator(cls):
        INTERFACE_REGISTRY[name] = cls
        return cls
    return decorator


def get_connector_class(name: str) -> Type[Any]:
    """
    Retrieve a connector class by name from the registry.
    
    Args:
        name: The name of the connector class to retrieve
        
    Returns:
        The connector class associated with the name
        
    Raises:
        KeyError: If no connector class is registered under the name
    """
    if name not in CONNECTOR_REGISTRY:
        raise KeyError(f"No connector class registered under name '{name}'")
    return CONNECTOR_REGISTRY[name]


def get_interface_class(name: str) -> Type[Any]:
    """
    Retrieve an interface class by name from the registry.
    
    Args:
        name: The name of the interface class to retrieve
        
    Returns:
        The interface class associated with the name
        
    Raises:
        KeyError: If no interface class is registered under the name
    """
    if name not in INTERFACE_REGISTRY:
        raise KeyError(f"No interface class registered under name '{name}'")
    return INTERFACE_REGISTRY[name]


def get_all_connectors() -> Dict[str, Type[Any]]:
    """
    Get all registered connector classes.
    
    Returns:
        A dictionary mapping names to connector classes
    """
    return CONNECTOR_REGISTRY.copy()


def get_all_interfaces() -> Dict[str, Type[Any]]:
    """
    Get all registered interface classes.
    
    Returns:
        A dictionary mapping names to interface classes
    """
    return INTERFACE_REGISTRY.copy()