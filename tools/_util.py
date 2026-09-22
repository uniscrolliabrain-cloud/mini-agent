"""Utilidades compartidas por las tools."""
import math


def clamp_int(value, default: int, low: int, high: int) -> int:
    """Convierte `value` a entero dentro de [low, high] (el LLM manda strings)."""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    if math.isnan(n):
        return default
    return max(low, min(high, n))


def escape_drive_query(value: str) -> str:
    """Escapa un literal para las queries de la Drive API (comillas simples)."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")
