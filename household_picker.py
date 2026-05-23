"""Who's training? household profile picker.

Shown after login when a household has >1 active profile and none is
selected. Selecting a profile sets it active (auth.set_active_player)
and reruns into the app as that profile.
"""
from __future__ import annotations
import streamlit as st

_PICKER_CSS = """
<style>
.hp-wrap { max-width: 760px; margin: 8vh auto 0; text-align: center; }
.hp-eyebrow { font-family:'Geist Mono',monospace; font-size:11px; font-weight:600;
  letter-spacing:0.24em; text-transform:uppercase; color:#E8C170; margin-bottom:12px; }
.hp-title { font-family:'Instrument Serif',serif; font-style:italic; font-weight:400;
  font-size:clamp(2.6rem,5vw,3.8rem); line-height:1.05; color:#F4EFE6; margin:0 0 36px; }
div[class*="st-key-hp_pick_"] button {
  width:100% !important; padding:26px 18px !important; border-radius:16px !important;
  background:rgba(244,239,230,0.025) !important; color:#F4EFE6 !important;
  border:1px solid rgba(244,239,230,0.10) !important;
  font-family:'Instrument Serif',serif !important; font-size:1.5rem !important;
  transition:all .2s ease !important;
}
div[class*="st-key-hp_pick_"] button:hover {
  border-color:rgba(232,193,112,0.5) !important; transform:translateY(-3px) !important;
  background:rgba(244,239,230,0.05) !important; }
.st-key-hp_add button {
  background:transparent !important; color:#C8C4BB !important;
  border:1px dashed rgba(244,239,230,0.18) !important; border-radius:16px !important;
  padding:26px 18px !important; width:100% !important;
  font-family:'Geist Mono',monospace !important; font-size:11px !important;
  letter-spacing:0.18em !important; text-transform:uppercase !important; }
</style>
"""


def render_household_picker(user_id: str) -> None:
    import auth
    st.markdown(_PICKER_CSS, unsafe_allow_html=True)
    st.markdown(
        "<div class=\"hp-wrap\"><div class=\"hp-eyebrow\">Your household</div>"
        "<h1 class=\"hp-title\">Who's training?</h1></div>",
        unsafe_allow_html=True,
    )
    profiles = auth.list_household_players(user_id)
    seats = auth.current_household_seats()
    n = len(profiles)
    cols = st.columns(min(max(n, 1), 4), gap="medium")
    for i, p in enumerate(profiles):
        with cols[i % 4]:
            meta = " · ".join(x for x in [str(p.get("position") or ""),
                              (p.get("handedness") or "")[:1]] if x)
            label = p.get("name") or "Player"
            if st.button(
                (label + "\n" + meta).strip(),
                key="hp_pick_" + str(p.get("id")),
                use_container_width=True,
            ):
                auth.set_active_player(p.get("id"))
                st.rerun()
    if n < seats:
        if st.button("+ Add a player", key="hp_add", use_container_width=True):
            st.session_state["page"] = "player_settings"
            st.session_state["_settings_open_section"] = "household"
            if profiles:
                auth.set_active_player(profiles[0].get("id"))
            st.rerun()
