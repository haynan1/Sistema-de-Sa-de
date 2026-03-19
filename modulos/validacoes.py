"""Validacoes compartilhadas do dominio."""

from __future__ import annotations

from datetime import datetime


def texto_obrigatorio(valor: str, campo: str) -> str:
    """Valida e normaliza um texto obrigatorio."""
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError(f"{campo} e obrigatorio.")
    return texto


def texto_opcional(valor: str | None) -> str:
    """Normaliza textos opcionais."""
    return str(valor or "").strip()


def texto_com_padrao(valor: str | None, padrao: str) -> str:
    """Retorna um texto informado ou um valor padrao amigavel."""
    texto = texto_opcional(valor)
    return texto or padrao


def data_iso(valor: str, campo: str) -> str:
    """Valida datas em formato ISO."""
    texto = texto_obrigatorio(valor, campo)
    try:
        datetime.strptime(texto, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{campo} deve estar no formato YYYY-MM-DD.") from exc
    return texto


def data_iso_opcional(valor: str | None, padrao: str, campo: str) -> str:
    """Retorna data valida ou usa um padrao quando o campo vier vazio."""
    texto = texto_opcional(valor)
    if not texto:
        return padrao
    return data_iso(texto, campo)


def inteiro_nao_negativo(valor: int | None, campo: str) -> int:
    """Valida inteiros nao negativos."""
    numero = int(valor or 0)
    if numero < 0:
        raise ValueError(f"{campo} nao pode ser negativo.")
    return numero


def numero_nao_negativo(valor: float | int | None, campo: str) -> float:
    """Valida numeros nao negativos."""
    numero = float(valor or 0)
    if numero < 0:
        raise ValueError(f"{campo} nao pode ser negativo.")
    return numero


def numero_positivo_opcional(valor: float | int | None, campo: str) -> float | None:
    """Valida numeros positivos opcionais."""
    if valor in (None, ""):
        return None
    numero = float(valor)
    if numero <= 0:
        raise ValueError(f"{campo} deve ser maior que zero.")
    return numero


def sexo_valido(valor: str) -> str:
    """Normaliza e valida sexo cadastral basico."""
    sexo = texto_obrigatorio(valor, "Sexo").upper()
    if sexo not in {"M", "F", "O"}:
        raise ValueError("Sexo deve ser M, F ou O.")
    return sexo
