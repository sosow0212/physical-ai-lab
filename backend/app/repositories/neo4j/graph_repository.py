"""Neo4j 그래프 저장소 — overview/impact traversal + 시드."""

import logging

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

# 노드 라벨: Line, Equipment, Sensor, Document
# 엣지: PART_OF, FEEDS(buffer_sec), AFFECTS(when,severity), MONITORS, ATTACHED_TO, DESCRIBES

#: 사용자 입력으로 생성 가능한 라벨/릴레이션 (Cypher 식별자는 파라미터화 불가 → 화이트리스트 검증)
ALLOWED_LABELS = frozenset({"Line", "Equipment", "Sensor"})
ALLOWED_REL_TYPES = frozenset(
    {"PART_OF", "FEEDS", "AFFECTS", "MONITORS", "ATTACHED_TO", "DESCRIBES"}
)

SEED_STATEMENTS = [
    "MATCH (n) DETACH DELETE n",  # noqa: E501 — 단일 문장
    """
    CREATE (line:Line {id: 'LINE-1', name: '1번 사출성형 라인'})
    """,
    """
    CREATE (ih:Equipment  {id: 'IH-250', name: '사출성형기',     type: '성형'}),
           (tcu:Equipment {id: 'TCU-100', name: '금형온도조절기', type: '온도제어'}),
           (ch:Equipment  {id: 'CH-200', name: '냉각수칠러',     type: '유틸리티'}),
           (cv1:Equipment {id: 'CV-01', name: '이송 컨베이어',   type: '이송'}),
           (cv2:Equipment {id: 'CV-02', name: '검사 컨베이어',   type: '이송'}),
           (cv3:Equipment {id: 'CV-03', name: '양품 컨베이어',   type: '이송'}),
           (vi:Equipment  {id: 'VI-200', name: '비전검사기',     type: '검사'}),
           (pl:Equipment  {id: 'PL-01', name: '팔레타이저',      type: '포장'}),
           (ac:Equipment  {id: 'AC-30', name: '스크류 컴프레서', type: '유틸리티'})
    """,
    """
    CREATE (ts1:Sensor {id: 'TS-01', name: '실린더온도', unit: '°C',
                       metric_name: 'cylinder_temp',
                       warning_threshold: 238.0, trip_threshold: 245.0,
                       is_lower_limit: false, base_mean: 220.0, base_std: 1.2}),
           (ts2:Sensor {id: 'TS-02', name: '금형온도', unit: '°C',
                       metric_name: 'mold_temperature',
                       warning_threshold: 64.0, trip_threshold: 68.0,
                       is_lower_limit: false, base_mean: 60.0, base_std: 0.6}),
           (ts3:Sensor {id: 'TS-03', name: '실내온도', unit: '°C',
                       metric_name: 'ambient_temp',
                       warning_threshold: 29.0, trip_threshold: 32.0,
                       is_lower_limit: false, base_mean: 24.0, base_std: 0.5}),
           (ps1:Sensor {id: 'PS-01', name: '냉각수압력', unit: 'MPa',
                       metric_name: 'chiller_pressure',
                       warning_threshold: 0.30, trip_threshold: 0.25,
                       is_lower_limit: true, base_mean: 0.42, base_std: 0.02}),
           (pair:Sensor {id: 'PS-AIR', name: '공기압력', unit: 'MPa',
                        metric_name: 'air_pressure',
                        warning_threshold: 0.60, trip_threshold: 0.50,
                        is_lower_limit: true, base_mean: 0.76, base_std: 0.03})
    """,
    """
    MATCH (line:Line {id: 'LINE-1'}) MATCH (e:Equipment)
    WHERE e.id IN ['IH-250','TCU-100','CH-200','CV-01','CV-02','CV-03','VI-200','PL-01','AC-30']
    CREATE (e)-[:PART_OF]->(line)
    """,
    """
    MATCH (ih {id:'IH-250'}), (cv1 {id:'CV-01'}), (vi {id:'VI-200'})
    MATCH (cv2 {id:'CV-02'}), (cv3 {id:'CV-03'}), (pl {id:'PL-01'})
    CREATE (ih)-[:FEEDS {buffer_sec: 90}]->(cv1),
           (cv1)-[:FEEDS]->(vi),
           (vi)-[:FEEDS]->(cv2),
           (vi)-[:FEEDS]->(cv3),
           (cv3)-[:FEEDS]->(pl)
    """,
    """
    MATCH (tcu {id:'TCU-100'}), (ih {id:'IH-250'}), (ch {id:'CH-200'}),
          (cv1 {id:'CV-01'}), (vi {id:'VI-200'}), (pl {id:'PL-01'}), (ac {id:'AC-30'})
    CREATE (tcu)-[:AFFECTS {when: '금형온도 +5°C 초과', severity: 'high'}]->(ih),
           (ch)-[:AFFECTS {when: '냉각수 온도/압력 저하', severity: 'high'}]->(tcu),
           (cv1)-[:AFFECTS {when: '정지 (버퍼 90초 소진)', severity: 'mid'}]->(ih),
           (vi)-[:AFFECTS {when: '오판정 (실내온도 30°C 초과)', severity: 'mid'}]->(pl),
           (ac)-[:AFFECTS {when: '공기압 0.5MPa 미만', severity: 'high'}]->(ih),
           (ac)-[:AFFECTS {when: '공기압 저하', severity: 'mid'}]->(cv1),
           (ac)-[:AFFECTS {when: '공기압 저하', severity: 'mid'}]->(vi)
    """,
    """
    MATCH (ts1 {id:'TS-01'}), (ts2 {id:'TS-02'}), (ts3 {id:'TS-03'}), (ps1 {id:'PS-01'}),
          (pair {id:'PS-AIR'}),
          (ih {id:'IH-250'}), (tcu {id:'TCU-100'}), (vi {id:'VI-200'}), (ch {id:'CH-200'}),
          (ac {id:'AC-30'})
    CREATE (ts1)-[:MONITORS]->(ih),
           (ts2)-[:MONITORS]->(tcu),
           (ts3)-[:MONITORS]->(vi),
           (ps1)-[:MONITORS]->(ch),
           (pair)-[:MONITORS]->(ac),
           (ts2)-[:ATTACHED_TO]->(ih)
    """,
]


class GraphRepository:
    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def reseed(self) -> dict:
        """개발용 전체 재시드 (기존 그래프 삭제 후 샘플 라인 생성)."""
        stats = {"nodes_deleted": 0, "nodes_created": 0, "relationships_created": 0}
        async with self._driver.session() as session:
            for statement in SEED_STATEMENTS:
                summary = await session.run(statement)
                counters = (await summary.consume()).counters
                stats["nodes_deleted"] += counters.nodes_deleted
                stats["nodes_created"] += counters.nodes_created
                stats["relationships_created"] += counters.relationships_created
        logger.info("그래프 재시드", extra=stats)
        return stats

    async def overview(self) -> dict:
        """전체 그래프를 프론트 force-graph 형식으로 반환."""
        query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, r, m
        """
        nodes: dict[str, dict] = {}
        links: list[dict] = []
        async with self._driver.session() as session:
            result = await session.run(query)
            async for record in result:
                node = record["n"]
                labels = list(node.labels) if node.labels else ["Unknown"]
                primary_label = labels[0]
                node_name = (
                    node.get("name")
                    or node.get("title")
                    or (
                        f"문서 ({node['id'][:8]}...)" if primary_label == "Document" else node["id"]
                    )
                )
                nodes[node["id"]] = {
                    "id": node["id"],
                    "name": node_name,
                    "label": primary_label,
                    "title": node.get("title"),
                    "props": dict(node),
                }
                rel, target = record["r"], record["m"]
                if rel is not None and target is not None:
                    links.append(
                        {
                            "source": node["id"],
                            "target": target["id"],
                            "type": rel.type,
                            "props": dict(rel),
                        }
                    )
                    tgt_labels = list(target.labels) if target.labels else ["Unknown"]
                    tgt_primary = tgt_labels[0]
                    tgt_name = (
                        target.get("name")
                        or target.get("title")
                        or (
                            f"문서 ({target['id'][:8]}...)"
                            if tgt_primary == "Document"
                            else target["id"]
                        )
                    )
                    nodes.setdefault(
                        target["id"],
                        {
                            "id": target["id"],
                            "name": tgt_name,
                            "label": tgt_primary,
                            "title": target.get("title"),
                            "props": dict(target),
                        },
                    )
        return {"nodes": list(nodes.values()), "links": links}

    async def impact(self, root_id: str, *, max_depth: int = 3) -> dict:
        """root(설비/센서)로부터 하류 영향범위 traversal.

        센서면 MONITORS/ATTACHED_TO 로 설비로 환산 후 FEEDS|AFFECTS*1..N 탐색.
        """
        # NOTE: Cypher는 가변 길이 경로(*1..N)에 파라미터를 쓸 수 없어 리터럴 3 고정
        resolve_and_traverse = """
        MATCH (root {id: $root_id})
        CALL {
            WITH root
            MATCH (e:Equipment)
            WHERE e = root OR (root)-[:MONITORS|ATTACHED_TO]->(e)
            RETURN e
        }
        MATCH path = (e)-[:FEEDS|AFFECTS*1..3]->(imp)
        RETURN root.id AS root, e.id AS via, imp.id AS impacted,
               labels(imp)[0] AS impacted_label, imp.name AS impacted_name,
               [r IN relationships(path) | type(r)] AS rels,
               length(path) AS depth
        ORDER BY depth
        """
        rows: list[dict] = []
        async with self._driver.session() as session:
            result = await session.run(resolve_and_traverse, root_id=root_id)
            async for record in result:
                rows.append(
                    {
                        "via": record["via"],
                        "impacted": record["impacted"],
                        "impacted_label": record["impacted_label"],
                        "impacted_name": record["impacted_name"],
                        "rels": record["rels"],
                        "depth": record["depth"],
                    }
                )
        root_name = rows[0].get("root", root_id)
        # 깊이별 정리 (같은 대상 최단 경로만)
        seen: dict[str, dict] = {}
        for row in rows:
            key = row["impacted"]
            if key not in seen or row["depth"] < seen[key]["depth"]:
                seen[key] = row
        items = sorted(seen.values(), key=lambda r: (r["depth"], r["impacted"]))
        return {"root": root_name, "items": items}

    async def describe_equipment(self, doc_id: str, title: str, codes: list[str]) -> None:
        """수집 완료 문서 → Document 노드 + DESCRIBES 엣지 (출처 연결)."""
        if not codes:
            return
        query = """
        MERGE (d:Document {mongo_id: $doc_id})
        SET d.title = $title, d.id = $doc_id, d.label_name = '매뉴얼'
        WITH d
        UNWIND $codes AS code
        MATCH (e {id: code})
        MERGE (d)-[:DESCRIBES]->(e)
        """
        async with self._driver.session() as session:
            await (await session.run(query, doc_id=doc_id, title=title, codes=codes)).consume()

    # ── CRUD (사용자 편집) ──

    async def monitor_profiles(self) -> list[dict]:
        """감시 대상 센서 프로파일 조회 — Sensor -[:MONITORS]-> Equipment + 임계치 props.

        조기 경보 시스템(EWS)의 단일 진실 공급원. 그래프 UI에서 센서 노드의
        warning_threshold/trip_threshold/unit/base_mean/base_std props를 편집하면
        EWS·시뮬레이터가 그대로 따라온다.
        """
        query = """
        MATCH (s:Sensor)-[:MONITORS]->(e:Equipment)
        RETURN e.id AS equipment_id, e.name AS equipment_name,
               s.id AS sensor_id,
               s.metric_name AS metric_name, s.unit AS unit,
               s.warning_threshold AS warning_threshold,
               s.trip_threshold AS trip_threshold,
               s.is_lower_limit AS is_lower_limit,
               s.base_mean AS base_mean, s.base_std AS base_std
        """
        rows: list[dict] = []
        async with self._driver.session() as session:
            result = await session.run(query)
            async for record in result:
                rows.append(dict(record))
        return rows

    async def auto_register_monitor(
        self, equipment_id: str, equipment_name: str, sensor_id: str, metric_name: str, unit: str
    ) -> None:
        """모르는 설비 텔레메트리 수신 시 Equipment+Sensor 자동 생성 (임계치는 미정)."""
        query = """
        MERGE (e:Equipment {id: $eq})
        SET e.name = coalesce(e.name, $eq_name), e.auto_registered = true
        MERGE (s:Sensor {id: $sensor})
        SET s.name = coalesce(s.name, $sensor),
            s.metric_name = coalesce(s.metric_name, $metric),
            s.unit = coalesce(s.unit, $unit),
            s.auto_registered = true
        MERGE (s)-[:MONITORS]->(e)
        """
        async with self._driver.session() as session:
            await (
                await session.run(
                    query,
                    eq=equipment_id,
                    eq_name=equipment_name,
                    sensor=sensor_id or f"{equipment_id}-S1",
                    metric=metric_name,
                    unit=unit,
                )
            ).consume()
        logger.info("모니터 대상 그래프 자동 등록", extra={"equipment_id": equipment_id})

    async def upsert_node(self, node_id: str, label: str, name: str, props: dict) -> dict:
        """노드 생성/갱신 (MERGE). 라벨은 화이트리스트로 검증한다."""
        if label not in ALLOWED_LABELS:
            raise ValueError(
                f"허용되지 않은 라벨: {label} ({'/'.join(sorted(ALLOWED_LABELS))} 중 선택)"
            )
        query = f"""
        MERGE (n:{label} {{id: $node_id}})
        SET n.name = $name, n += $props
        RETURN n.id AS id, n.name AS name, labels(n)[0] AS label
        """
        async with self._driver.session() as session:
            result = await session.run(query, node_id=node_id, name=name, props=props or {})
            record = await result.single()
        logger.info("그래프 노드 저장", extra={"node_id": node_id, "label": label})
        return dict(record)

    async def delete_node(self, node_id: str) -> int:
        """노드 + 연결 엣지 삭제 (DETACH DELETE). 삭제된 노드 수 반환."""
        async with self._driver.session() as session:
            summary = await session.run(
                "MATCH (n {id: $node_id}) DETACH DELETE n RETURN count(n) AS c",
                node_id=node_id,
            )
            record = await summary.single()
        logger.info("그래프 노드 삭제", extra={"node_id": node_id})
        return record["c"] if record else 0

    async def upsert_edge(self, source: str, target: str, rel_type: str, props: dict) -> dict:
        """엣지 생성/갱신 (MERGE). 릴레이션 타입은 화이트리스트로 검증한다."""
        if rel_type not in ALLOWED_REL_TYPES:
            raise ValueError(
                f"허용되지 않은 관계: {rel_type} ({'/'.join(sorted(ALLOWED_REL_TYPES))} 중 선택)"
            )
        query = f"""
        MATCH (a {{id: $source}}), (b {{id: $target}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN a.id AS source, b.id AS target, type(r) AS type
        """
        async with self._driver.session() as session:
            result = await session.run(query, source=source, target=target, props=props or {})
            record = await result.single()
        if record is None:
            raise ValueError(f"노드를 찾을 수 없습니다: {source} 또는 {target}")
        logger.info("그래프 엣지 저장", extra={"source": source, "target": target, "rel": rel_type})
        return dict(record)

    async def delete_edge(self, source: str, target: str, rel_type: str) -> int:
        """엣지 삭제. 삭제된 수 반환."""
        if rel_type not in ALLOWED_REL_TYPES:
            raise ValueError(f"허용되지 않은 관계: {rel_type}")
        query = f"""
        MATCH (a {{id: $source}})-[r:{rel_type}]->(b {{id: $target}})
        DELETE r RETURN count(r) AS c
        """
        async with self._driver.session() as session:
            summary = await session.run(query, source=source, target=target)
            record = await summary.single()
        return record["c"] if record else 0
