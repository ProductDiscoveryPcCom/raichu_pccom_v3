"""
Tests for config/arquetipos.py — archetype schema validation.
"""
from config.arquetipos import (
    ARQUETIPOS,
    MIN_GUIDING_QUESTIONS,
    get_arquetipo,
    get_arquetipo_names,
    get_guiding_questions,
    validate_arquetipo_completeness,
)


REQUIRED_KEYS = {
    "code", "name", "description", "tone", "structure",
    "default_length", "min_length", "max_length", "visual_elements",
}


def test_all_arquetipos_required_keys():
    """Every archetype must have the minimum required keys."""
    for code, data in ARQUETIPOS.items():
        missing = REQUIRED_KEYS - set(data.keys())
        assert not missing, f"{code} missing keys: {missing}"
        assert isinstance(data["structure"], list), f"{code} structure must be list"
        assert isinstance(data["visual_elements"], list), f"{code} visual_elements must be list"


def test_arquetipos_length_ranges():
    """min < default <= max for every archetype."""
    for code, data in ARQUETIPOS.items():
        assert data["min_length"] < data["default_length"], (
            f"{code}: min_length ({data['min_length']}) >= default_length ({data['default_length']})"
        )
        assert data["default_length"] <= data["max_length"], (
            f"{code}: default_length ({data['default_length']}) > max_length ({data['max_length']})"
        )


def test_get_arquetipo():
    arq1 = get_arquetipo("ARQ-1")
    assert arq1 is not None
    assert arq1["code"] == "ARQ-1"
    assert get_arquetipo("ARQ-999") is None


def test_get_arquetipo_names():
    names = get_arquetipo_names()
    assert isinstance(names, dict)
    assert len(names) == len(ARQUETIPOS)
    for code, name in names.items():
        assert isinstance(name, str)
        assert name  # non-empty


def test_all_arquetipos_have_min_guiding_questions():
    """R2.5: cada arquetipo debe tener al menos MIN_GUIDING_QUESTIONS preguntas
    específicas (sin contar las universales). Si baja, ajustar arquetipos.py."""
    failures = []
    for code in ARQUETIPOS:
        questions = get_guiding_questions(code, include_universal=False)
        if len(questions) < MIN_GUIDING_QUESTIONS:
            failures.append(f"{code}: {len(questions)} preguntas (mínimo {MIN_GUIDING_QUESTIONS})")
    assert not failures, "Arquetipos con guiding_questions insuficientes:\n  " + "\n  ".join(failures)


def test_validate_arquetipo_completeness_returns_true_for_all():
    """R2.5: validate_arquetipo_completeness no debe disparar WARNING en ningún arquetipo del catálogo."""
    for code in ARQUETIPOS:
        assert validate_arquetipo_completeness(code), f"{code} falla validación de completeness"


def test_validate_arquetipo_completeness_unknown_code():
    """validate_arquetipo_completeness retorna False para códigos desconocidos sin lanzar."""
    assert validate_arquetipo_completeness("ARQ-999") is False
