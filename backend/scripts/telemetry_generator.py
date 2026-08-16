#!/usr/bin/env python3
"""CLI용 모의 공정 데이터 Generator 스크립트.

사용법:
  python -m scripts.telemetry_generator --scenario NORMAL --hz 5
  python -m scripts.telemetry_generator --scenario ANOMALY_40 --hz 10
  python -m scripts.telemetry_generator --scenario CRITICAL_SPIKE
"""

import argparse
import asyncio
import contextlib
import signal
import sys

from app.core.config import get_settings
from app.infrastructure.kafka import create_producer, stop_producer
from app.schemas.telemetry import ScenarioType
from app.services.telemetry_service import TelemetryGenerator


async def main() -> None:
    parser = argparse.ArgumentParser(description="LINE-1 모의 텔레메트리 생성기")
    parser.add_argument(
        "--scenario",
        type=str,
        default="NORMAL",
        choices=["NORMAL", "ANOMALY_40", "ANOMALY_70", "CRITICAL_SPIKE", "DRIFT"],
        help="시뮬레이션 시나리오",
    )
    parser.add_argument("--hz", type=int, default=5, help="초당 발송 건수 (1~50)")
    parser.add_argument("--seconds", type=int, default=0, help="실행 시간(초), 0이면 무한")
    args = parser.parse_args()

    settings = get_settings()
    producer = await create_producer(settings)
    generator = TelemetryGenerator(producer, settings)

    scenario_enum = ScenarioType(args.scenario)
    generator.start(hz=args.hz, scenario=scenario_enum)
    print(f"🚀 텔레메트리 제너레이터 가동 (시나리오: {args.scenario}, 속도: {args.hz} Hz)")
    print("종료하려면 Ctrl+C 를 누르세요...")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    try:
        if args.seconds > 0:
            await asyncio.wait_for(stop_event.wait(), timeout=args.seconds)
        else:
            await stop_event.wait()
    except TimeoutError:
        print(f"\n지정된 {args.seconds}초 경과로 종료합니다.")
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        generator.stop()
        await stop_producer(producer)
        print("정상 종료되었습니다.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
