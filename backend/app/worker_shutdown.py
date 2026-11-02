"""Finish the current unit of work before a deployment replaces this process."""

import asyncio
import signal


def shutdown_event():
    event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(name, event.set)
        except NotImplementedError:  # Production workers run on Linux.
            pass
    return event


async def pause(event, seconds):
    try:
        await asyncio.wait_for(event.wait(), timeout=seconds)
    except TimeoutError:
        pass
