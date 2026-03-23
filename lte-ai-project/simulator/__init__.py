"""
Simulator Package

Contains error injection and error definitions for network simulation.
"""

from .error_definitions import (
    ErrorType,
    ErrorDefinition,
    ERROR_CATALOG,
    KPIImpactCalculator,
    validate_error_type,
    get_all_error_types
)

__all__ = [
    "ErrorType",
    "ErrorDefinition",
    "ERROR_CATALOG",
    "KPIImpactCalculator",
    "validate_error_type",
    "get_all_error_types"
]
