"""
Shared Cross-Cutting Kernel.

Contains the foundational abstractions shared by every bounded context of the
casino platform: immutable value objects, the typed exception hierarchy,
auditable/versioned entity base classes, and re-usable design pattern
building blocks (abstract factory, abstract builder, specification).

No module in this package may depend on a bounded context or on the Telegram
framework. It is the purest layer of the platform.
"""
