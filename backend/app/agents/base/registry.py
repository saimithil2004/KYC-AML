import logging
import threading
from typing import Dict, Type, List, Optional, Any
from app.agents.base.base_agent import BaseAgent
from app.agents.base.exceptions import RegistryError

logger = logging.getLogger(__name__)

class AgentRegistry:
    """
    Thread-safe Singleton Agent Registry.
    Supports dependency injection, dynamic loading, and plugin integration.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AgentRegistry, cls).__new__(cls)
                cls._instance._registry = {}
            return cls._instance

    @classmethod
    def register(cls, name: str):
        """Decorator to register an Agent class by name."""
        def decorator(subclass: Type[BaseAgent]):
            registry_inst = cls.get_registry()
            with registry_inst._lock:
                if name in registry_inst._registry:
                    logger.warning(f"Overwriting already registered agent: {name}")
                registry_inst._registry[name] = subclass
                logger.info(f"Registered agent '{name}' to registry index.")
                return subclass
        return decorator

    def register_agent_class(self, name: str, agent_class: Type[BaseAgent]):
        """Manually registers an agent class (for plugin/dynamic loading support)."""
        with self._lock:
            self._registry[name] = agent_class
            logger.info(f"Manually registered agent class '{name}'")

    def unregister(self, name: str):
        """Unregisters an agent by name."""
        with self._lock:
            if name in self._registry:
                del self._registry[name]
                logger.info(f"Unregistered agent '{name}' successfully.")

    def get_agent(self, name: str, db_session: Optional[Any] = None) -> BaseAgent:
        """Resolves agent from index with Dependency Injection support."""
        agent_class = self._registry.get(name)
        if not agent_class:
            raise RegistryError(f"Agent '{name}' not found in registry index.")
        from app.agents.base.agent_context import AgentContext
        context = AgentContext(db_session=db_session)
        return agent_class(context=context)

    def list_agents(self) -> List[str]:
        """Lists all registered agent names."""
        return list(self._registry.keys())

    @classmethod
    def get_registry(cls) -> "AgentRegistry":
        """Singleton accessor helper."""
        return cls()
