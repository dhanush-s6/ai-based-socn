import yaml
import os
from pathlib import Path
from typing import Any, Dict

class ConfigManager:
    """Centralized configuration manager for the entire system."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from YAML file."""
        config_path = Path(__file__).parent / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            print(f"✓ Configuration loaded from {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Example:
            config.get("simulator.num_enbs")  # Returns 6
            config.get("ai_engine.server_port")  # Returns 5000
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section."""
        return self._config.get(section, {})
    
    def reload(self):
        """Reload configuration from file."""
        self._load_config()
    
    def dump(self) -> Dict[str, Any]:
        """Get the entire configuration as a dictionary."""
        return self._config.copy()


# Singleton instance
config = ConfigManager()


# Convenience functions
def get_config(key: str, default: Any = None) -> Any:
    """Convenience function to get config value."""
    return config.get(key, default)


def get_config_section(section: str) -> Dict[str, Any]:
    """Convenience function to get config section."""
    return config.get_section(section)
