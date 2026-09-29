import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.app.core.events import get_event_bus
from backend.app.core.logging import get_logger
from backend.app.llm.cooldown import cooldown_tracker
from backend.app.llm.defaults import get_default_roles_config
from backend.app.llm.exceptions import AllProvidersExhaustedError
from backend.app.llm.types import ModelRole, ModelRolesConfig

logger = get_logger("niko.llm.deferred_queue")


@dataclass
class DeferredChatRequest:
    request_id: str
    user_id: str
    user_message: str
    conversation_id: str | None = None
    role: ModelRole | str = ModelRole.CHAT
    source: str | None = None
    is_external: bool = False
    elevated_mode: bool = False
    enqueued_at: float = field(default_factory=time.time)
    future: asyncio.Future | None = None
    on_complete: Callable[[dict[str, Any]], Any] | None = None
    on_error: Callable[[Exception], Any] | None = None


class DeferredQueue:
    """
    Manages deferred chat completions when all providers for a role are in cooldown.
    Emits cooldown banner events and automatically retries requests when cooldown windows expire.
    """

    def __init__(
        self,
        roles_config: ModelRolesConfig | None = None,
        retry_interval_min: float = 0.5,
    ) -> None:
        self.roles_config = roles_config or get_default_roles_config()
        self.retry_interval_min = retry_interval_min
        self._queue: list[DeferredChatRequest] = []
        self._lock = asyncio.Lock()
        self._wake_event = asyncio.Event()
        self._worker_task: asyncio.Task | None = None
        self._running = False
        self._active_banner: dict[str, Any] | None = None

    @property
    def active_banner(self) -> dict[str, Any] | None:
        return self._active_banner

    def get_shortest_reset_for_role(self, role: ModelRole | str) -> float:
        """Calculate the shortest remaining cooldown in seconds for targets of a role."""
        targets = self.roles_config.get_role_targets(role)
        return cooldown_tracker.get_shortest_cooldown_for_targets(targets)

    async def emit_cooldown_banner(self, role: ModelRole | str, shortest_reset: float) -> dict[str, Any]:
        """Publish the cooldown banner event to the event bus."""
        role_str = role.value if isinstance(role, ModelRole) else str(role)
        reset_seconds = max(1, int(round(shortest_reset)))
        message = f"all providers cooling down, shortest reset in {reset_seconds}s"

        banner_payload = {
            "role": role_str,
            "shortest_reset_seconds": shortest_reset,
            "message": message,
            "timestamp": time.time(),
        }
        self._active_banner = banner_payload

        event_bus = get_event_bus()
        await event_bus.publish(
            topic="chat",
            event_type="cooldown_banner",
            payload=banner_payload,
        )
        await event_bus.publish(
            topic="sys",
            event_type="cooldown_banner",
            payload=banner_payload,
        )
        logger.warning("All providers cooling down", role=role_str, message=message)
        return banner_payload

    async def clear_cooldown_banner(self) -> None:
        """Emit cooldown cleared event when providers become available."""
        if self._active_banner:
            self._active_banner = None
            event_bus = get_event_bus()
            await event_bus.publish(
                topic="chat",
                event_type="cooldown_cleared",
                payload={"message": "cooldown ended, requests resumed", "timestamp": time.time()},
            )
            await event_bus.publish(
                topic="sys",
                event_type="cooldown_cleared",
                payload={"message": "cooldown ended, requests resumed", "timestamp": time.time()},
            )
            logger.info("Cooldown ended, providers available again")

    async def enqueue(self, request: DeferredChatRequest) -> DeferredChatRequest:
        """Add request to the deferred queue, emit cooldown banner, and wake background worker."""
        shortest_reset = self.get_shortest_reset_for_role(request.role)

        async with self._lock:
            self._queue.append(request)

        await self.emit_cooldown_banner(request.role, shortest_reset)
        self._wake_event.set()
        return request

    async def cancel(self, request_id: str) -> bool:
        """Cancel a pending deferred request."""
        async with self._lock:
            for i, req in enumerate(self._queue):
                if req.request_id == request_id:
                    self._queue.pop(i)
                    if req.future and not req.future.done():
                        req.future.cancel()
                    if not self._queue:
                        await self.clear_cooldown_banner()
                    return True
        return False

    async def list_queued(self) -> list[DeferredChatRequest]:
        async with self._lock:
            return list(self._queue)

    def start_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._running = True
            self._worker_task = asyncio.create_task(self._process_queue_loop())

    def stop_worker(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

    async def _process_queue_loop(self) -> None:
        """Background worker that waits for cooldown windows to end and retries requests."""
        while self._running:
            try:
                # Wait until there are items or wake signal
                if not self._queue:
                    await self._wake_event.wait()
                    self._wake_event.clear()

                if not self._running:
                    break

                async with self._lock:
                    if not self._queue:
                        continue
                    current_req = self._queue[0]

                # Determine sleep time based on shortest reset
                shortest_reset = self.get_shortest_reset_for_role(current_req.role)
                if shortest_reset > 0:
                    await self.emit_cooldown_banner(current_req.role, shortest_reset)
                    wait_time = max(self.retry_interval_min, min(shortest_reset, 15.0))
                    try:
                        await asyncio.sleep(wait_time)
                    except asyncio.CancelledError:
                        break

                # Attempt execution after cooldown
                async with self._lock:
                    if not self._queue:
                        continue
                    req = self._queue.pop(0)

                await self._execute_deferred(req)

                async with self._lock:
                    if not self._queue:
                        await self.clear_cooldown_banner()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in deferred queue processor", error=str(e))
                await asyncio.sleep(1.0)

    async def _execute_deferred(self, req: DeferredChatRequest) -> None:
        """Execute a popped deferred request via ChatService."""
        try:
            from backend.app.db.session import get_session_maker
            from backend.app.services.chat_service import ChatService

            session_maker = get_session_maker()
            async with session_maker() as db:
                chat_svc = ChatService(db=db)
                result = await chat_svc.chat(
                    conversation_id=req.conversation_id,
                    user_id=req.user_id,
                    user_message=req.user_message,
                    source=req.source,
                    is_external=req.is_external,
                    role=req.role,
                    elevated_mode=req.elevated_mode,
                )
                await db.commit()

            if req.on_complete:
                req.on_complete(result)
            if req.future and not req.future.done():
                req.future.set_result(result)

        except AllProvidersExhaustedError:
            # Re-enqueue at the front if still exhausted
            logger.info("Deferred request still exhausted, re-scheduling", request_id=req.request_id)
            async with self._lock:
                self._queue.insert(0, req)
        except Exception as e:
            logger.error("Failed executing deferred request", request_id=req.request_id, error=str(e))
            if req.on_error:
                req.on_error(e)
            if req.future and not req.future.done():
                req.future.set_exception(e)


# Global singleton deferred queue
deferred_queue = DeferredQueue()
