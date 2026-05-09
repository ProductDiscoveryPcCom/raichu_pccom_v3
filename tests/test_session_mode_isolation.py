"""Tests de aislamiento de session_state entre modos (R2.6)."""
import pytest

from core.session import (
    _MODE_RESULT_KEYS,
    _save_mode_results,
    _restore_mode_results,
)


class FakeSessionState(dict):
    """Sustituto de st.session_state — dict con acceso por atributo."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(key) from e

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as e:
            raise AttributeError(key) from e


@pytest.fixture
def fake_session_state(monkeypatch):
    fake = FakeSessionState()
    import core.session as session_mod
    monkeypatch.setattr(session_mod.st, "session_state", fake, raising=False)
    return fake


def test_mode_result_keys_includes_gsc_and_feedback():
    """_MODE_RESULT_KEYS debe cubrir verify (gsc_*) y feedback keys (R2.6)."""
    expected_added = {
        'gsc_analysis',
        'gsc_opportunities_data',
        '_post_gen_checks',
        '_refinement_feedback',
        '_translation_feedback',
        '_batch_translation_feedback',
    }
    assert expected_added.issubset(set(_MODE_RESULT_KEYS))


def test_mode_isolation_does_not_leak_gsc_analysis(fake_session_state):
    """Cambiar de verify -> new no debe filtrar gsc_analysis ni _post_gen_checks."""
    fake_session_state['gsc_analysis'] = {'queries': ['foo'], 'canibalization': True}
    fake_session_state['_post_gen_checks'] = {'check1': True}

    _save_mode_results('verify')

    assert 'gsc_analysis' not in fake_session_state
    assert '_post_gen_checks' not in fake_session_state
    assert '_saved_results_verify' in fake_session_state

    _restore_mode_results('new')  # 'new' no tiene snapshot previo

    assert 'gsc_analysis' not in fake_session_state
    assert '_post_gen_checks' not in fake_session_state


def test_mode_isolation_round_trip_restores_state(fake_session_state):
    """Volver al modo de origen debe restaurar el snapshot completo."""
    fake_session_state['gsc_analysis'] = {'queries': ['foo']}
    fake_session_state['_refinement_feedback'] = ['issue-a']
    fake_session_state['draft_html'] = '<p>x</p>'

    _save_mode_results('verify')
    _restore_mode_results('new')          # entra en new, vacío
    _save_mode_results('new')             # sale de new (vacío) -> guarda
    _restore_mode_results('verify')       # vuelve a verify

    assert fake_session_state['gsc_analysis'] == {'queries': ['foo']}
    assert fake_session_state['_refinement_feedback'] == ['issue-a']
    assert fake_session_state['draft_html'] == '<p>x</p>'


def test_translation_keys_also_isolated(fake_session_state):
    """Las keys translated_html_* (dinámicas) también se aíslan por modo."""
    fake_session_state['translated_html_fr'] = '<p>bonjour</p>'
    fake_session_state['translated_html_en'] = '<p>hello</p>'

    _save_mode_results('new')

    assert 'translated_html_fr' not in fake_session_state
    assert 'translated_html_en' not in fake_session_state

    _restore_mode_results('new')

    assert fake_session_state['translated_html_fr'] == '<p>bonjour</p>'
    assert fake_session_state['translated_html_en'] == '<p>hello</p>'
