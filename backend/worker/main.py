"""수집 워커 진입점.

Phase 0: 자리만 잡은 플레이스홀더 — 정상 기동/종료(graceful shutdown)만 확인.
Phase 2: Kafka consumer 루프로 대체된다.
"""

import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker 시작 (플레이스홀더 — 실제 consumer는 Phase 2 구현)")
    await stop.wait()
    logger.info("worker 종료")


if __name__ == "__main__":
    asyncio.run(main())
