"""agents package.

Marks ``agents`` as a regular package. Intentionally free of import-time side
effects so that importing an individual agent module stays cheap. Registry
wiring lives in :mod:`agents.bootstrap`.
"""
