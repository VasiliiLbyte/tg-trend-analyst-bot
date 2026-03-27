from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.rank import RankedItem


@dataclass(frozen=True, slots=True)
class PreparedPost:
    kind: str  # digest | deep_dive
    item_ids: tuple[int, ...]
    messages: tuple[str, ...]


def split_telegram_messages(text: str, *, max_len: int = 4096) -> tuple[str, ...]:
    if len(text) <= max_len:
        return (text,)

    parts: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in text.splitlines(True):
        rest = line
        while rest:
            space_left = max_len - cur_len
            if space_left <= 0 and cur:
                parts.append("".join(cur).rstrip())
                cur = []
                cur_len = 0
                space_left = max_len

            if len(rest) <= space_left:
                cur.append(rest)
                cur_len += len(rest)
                rest = ""
            else:
                chunk = rest[:space_left]
                cur.append(chunk)
                parts.append("".join(cur).rstrip())
                cur = []
                cur_len = 0
                rest = rest[space_left:]
    if cur:
        parts.append("".join(cur).rstrip())
    return tuple(p for p in parts if p)


def compose_digest(
    *,
    ranked: tuple[RankedItem, ...],
    top_k: int = 7,
) -> PreparedPost:
    top = ranked[:top_k]
    lines: list[str] = []
    lines.append("Дайджест трендов за последние часы")
    lines.append("")
    for i, r in enumerate(top, start=1):
        emoji = "🚀" if r.category == "tech_breakthrough" else ("📈" if r.category == "business_trend" else "🧩")
        lines.append(f"{emoji} {i}. {r.item.title}")
        lines.append(f"Источник: {r.item.url}")
        lines.append("")
    lines.append("Что делать бизнесу")
    lines.append("- Проверьте, затрагивает ли это ваших клиентов/рынок")
    lines.append("- Сформулируйте гипотезу и быстрый эксперимент на 1–2 недели")
    lines.append("")
    lines.append("Почему важно сейчас")
    lines.append("- Сигналы усиливаются: меняется стоимость, скорость и доступность технологий")

    text = "\n".join(lines).strip()
    return PreparedPost(
        kind="digest",
        item_ids=tuple(r.item.id for r in top if getattr(r.item, "id", None) is not None),
        messages=split_telegram_messages(text),
    )

