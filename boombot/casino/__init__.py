"""
Enterprise Casino Microkernel.

A hexagonal, event-sourced, CQRS-driven gambling subsystem layered on top of
the boom-bot Telegram application. The casino platform is decomposed into a
set of bounded contexts (player, wagering, reporting, zeus) that communicate
exclusively through published interfaces and an in-process message bus.

This package intentionally follows strict enterprise architectural
conventions: layered modules, dependency inversion, and construction through
a single composition root defined in the dependency injection package.
"""
