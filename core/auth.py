"""
Autenticación por contraseña para la aplicación Streamlit.

Lee la contraseña de st.secrets['app']['password'].
"""

import hmac
import streamlit as st


def check_auth() -> bool:
    """
    Verifica autenticación por contraseña.
    Lee la contraseña de st.secrets['app']['password'].

    Returns:
        True si autenticado, False si no
    """
    # Si ya está autenticado en esta sesión, no pedir de nuevo
    if st.session_state.get('authenticated'):
        return True

    # Obtener contraseña configurada
    app_password = None
    try:
        app_password = st.secrets.get('app', {}).get('password')
    except Exception:
        pass

    # Si no hay contraseña configurada, permitir acceso libre
    if not app_password:
        return True

    # Mostrar formulario de login
    st.markdown(
        """
        <div style="max-width: 400px; margin: 80px auto; text-align: center;">
            <h2>🚀 Raichu Content Generator</h2>
            <p style="color: #666;">Introduce la contraseña para acceder</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        password_input = st.text_input(
            "Contraseña",
            type="password",
            key="login_password",
            placeholder="••••••••",
        )

        if st.button("Entrar", use_container_width=True, key="btn_login"):
            if hmac.compare_digest(password_input, app_password):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")

    return False
