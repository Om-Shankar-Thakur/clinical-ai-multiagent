"""
core.registry
=============
Name -> agent resolution.

The executor asks the registry for agents by name (``registry.get("lab_agent")``)
and therefore never imports concrete agent classes. New agents are added by
registering a factory; no executor change is required.

Agents are registered as zero-argument *factories* (callables) and instantiated
lazily on first use, then cached as singletons. Lazy instantiation matters here
because several agents load heavy resources (FAISS indices, embedding model) in
their constructors - we only pay for the agents a given plan actually uses.
"""

from __future__ import annotations

from typing import Callable

from core.base_agent import BaseAgent


class AgentRegistry:
    """A lazy, singleton-caching registry of agent factories."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], BaseAgent]] = {}
        self._instances: dict[str, BaseAgent] = {}

    def register(self, name: str, factory: Callable[[], BaseAgent]) -> None:
        """Register a zero-arg factory that builds the agent on demand."""
        if name in self._factories:
            raise ValueError(f"Agent '{name}' is already registered.")
        self._factories[name] = factory

    def is_registered(self, name: str) -> bool:
        return name in self._factories

    def get(self, name: str) -> BaseAgent:
        """Return the (cached) agent instance for ``name``."""
        if name not in self._factories:
            raise KeyError(
                f"Agent '{name}' is not registered. "
                f"Available agents: {sorted(self._factories)}"
            )
        if name not in self._instances:
            self._instances[name] = self._factories[name]()
        return self._instances[name]

    def available(self) -> list[str]:
        """Names of all registered agents."""
        return sorted(self._factories)
