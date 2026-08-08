from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from packages.common.config import get_settings

OUTPUT = Path("data") / "aggregates_2026.csv"


async def export_aggregates(database_url: str, output: Path) -> int:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT u.code AS university,
                               sg.title AS group_title,
                               sg.campaign_year AS campaign_year,
                               s.fetched_at AS snapshot_date,
                               s.row_count AS applications,
                               COALESCE((s.raw_payload -> 'seat_counts')::text, '') AS seat_counts,
                               (
                                   SELECT min(a.competitive_score)
                                   FROM applications a
                                   WHERE a.snapshot_id = s.id
                                     AND (
                                       a.application_status LIKE 'Включен в приказ%'
                                       OR a.application_status IN ('in_order', 'Зачислен')
                                     )
                                     AND a.competitive_score > 0
                               ) AS min_enrolled_score,
                               (
                                   SELECT max(a.rank)
                                   FROM applications a
                                   WHERE a.snapshot_id = s.id
                               ) AS last_rank
                        FROM list_snapshots s
                        JOIN competition_groups sg ON sg.id = s.competition_group_id
                        JOIN universities u ON u.id = sg.university_id
                        WHERE s.id IN (
                            SELECT DISTINCT ON (sg2.id) s2.id
                            FROM list_snapshots s2
                            JOIN competition_groups sg2 ON sg2.id = s2.competition_group_id
                            WHERE s2.status = 'valid'
                            ORDER BY sg2.id, s2.fetched_at DESC
                        )
                        ORDER BY u.code, sg.title
                        """
                    )
                )
            ).mappings()
            records = [dict(row) for row in rows]
    finally:
        await engine.dispose()

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "university",
                "group_title",
                "campaign_year",
                "snapshot_date",
                "applications",
                "seat_counts",
                "min_enrolled_score",
                "last_rank",
            ],
        )
        writer.writeheader()
        writer.writerows(records)
    return len(records)


async def main() -> None:
    settings = get_settings()
    count = await export_aggregates(str(settings.database_url), OUTPUT)
    print(f"exported {count} groups to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
