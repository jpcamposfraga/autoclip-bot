import streamlit as st
import time
from datetime import datetime, timedelta
from pathlib import Path
import config
from config import CLIPS_DIR
import clipper
import emulator
import db
import scheduler
import metrics

st.set_page_config(
    page_title="AutoClip Factory",
    page_icon="🎬",
    layout="wide"
)

# Start background scheduler thread
scheduler.start_scheduler()

# Initialize Session State
if "gemini_key" not in st.session_state:
    st.session_state["gemini_key"] = config.load_gemini_key()
if "generated_clips" not in st.session_state:
    st.session_state["generated_clips"] = []

# Sidebar
with st.sidebar:
    st.title("🎬 AutoClip Studio")
    
    gemini_key_input = st.text_input(
        "Gemini API Key",
        value=st.session_state["gemini_key"],
        type="password",
        help="Obtenha sua chave gratuita no Google AI Studio (será salva automaticamente)"
    )
    if gemini_key_input and gemini_key_input != st.session_state["gemini_key"]:
        st.session_state["gemini_key"] = gemini_key_input
        config.save_gemini_key(gemini_key_input)
        st.toast("Chave de API salva com sucesso!", icon="💾")
    elif gemini_key_input and not config.load_gemini_key():
        config.save_gemini_key(gemini_key_input)

    st.divider()
    st.subheader("📱 Emulador Ativo")
    devices = emulator.get_connected_devices()
    if devices:
        st.success(f"{len(devices)} dispositivo(s) online:")
        selected_device = st.selectbox("Dispositivo Conectado", devices)
    else:
        st.warning("Nenhum emulador ADB detectado.")
        selected_device = None

    with st.expander("🔌 Conexão Manual ADB"):
        custom_addr = st.text_input("Endereço", value="127.0.0.1:5555", help="127.0.0.1:5555 para LDPlayer")
        if st.button("Conectar Manualmente"):
            res = emulator.connect_device(custom_addr)
            st.info(f"Resposta: {res}")
            st.rerun()

    if st.button("🔄 Atualizar Emuladores", use_container_width=True):
        st.rerun()

# Main Application Tabs
tab_create, tab_queue, tab_metrics, tab_emulators, tab_settings = st.tabs([
    "🎬 Criador de Cortes (IA)",
    "📅 Fila de Postagens",
    "📊 Dashboard de Métricas",
    "📱 Controle de Emuladores",
    "⚙️ Configurações & Templates"
])

# TAB 1: Criador de Cortes
with tab_create:
    st.header("Gerar Cortes Virais a partir do YouTube")
    yt_url = st.text_input(
        "URL do Clipe no YouTube",
        placeholder="https://www.youtube.com/watch?v=..."
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        max_clips = st.slider("Máximo de cortes a extrair", min_value=1, max_value=5, value=3)
    with col2:
        st.write("")
        st.write("")
        start_btn = st.button("⚡ Processar e Gerar Cortes 9:16", type="primary", use_container_width=True)

    if start_btn:
        if not yt_url:
            st.error("Por favor, insira uma URL válida do YouTube.")
        elif not st.session_state["gemini_key"]:
            st.error("Insira sua Gemini API Key na barra lateral para prosseguir.")
        else:
            status_box = st.status("Iniciando pipeline de corte...", expanded=True)
            try:
                # 1. Download
                status_box.update(label="1/4 Baixando clipe em alta definição...")
                video_id = f"clip_{int(time.time())}"
                video_path = clipper.download_youtube(yt_url, video_id=video_id)

                # 2. Extração de Áudio
                status_box.update(label="2/4 Extraindo áudio para análise...")
                audio_path = clipper.extract_audio(video_path)

                # 3. Análise com Gemini (Multi-clip)
                status_box.update(label="3/4 IA identificando ganchos virais e gerando legendas...")
                clips_data = clipper.analyze_scene_with_gemini(
                    audio_path,
                    st.session_state["gemini_key"],
                    max_clips=max_clips,
                    status_callback=lambda msg: status_box.update(label=f"3/4 {msg}")
                )

                if not clips_data:
                    raise RuntimeError("Nenhum segmento viral válido foi identificado no áudio fornecido.")

                # 4. Renderização Vertical em Lote
                status_box.update(label=f"4/4 Renderizando {len(clips_data)} corte(s) em 9:16 com legendas...")
                rendered_clips = clipper.render_clips_batch(
                    video_path=video_path,
                    clips_data=clips_data,
                    video_id=video_id,
                    status_callback=lambda msg: status_box.update(label=f"4/4 {msg}")
                )

                st.session_state["generated_clips"] = rendered_clips
                status_box.update(label=f"✅ {len(rendered_clips)} corte(s) concluído(s) com sucesso!", state="complete")
            except Exception as e:
                status_box.update(label=f"❌ Erro durante o processamento: {e}", state="error")
                st.exception(e)

    # Exibição dos cortes gerados
    if st.session_state["generated_clips"]:
        st.divider()
        st.subheader(f"🎬 Cortes Gerados ({len(st.session_state['generated_clips'])})")

        for idx, clip in enumerate(st.session_state["generated_clips"]):
            dur = round(clip.get("end_seconds", 0) - clip.get("start_seconds", 0), 1)
            with st.expander(f"Corte #{clip.get('part', idx+1)}: {clip.get('title', 'Sem título')} ({dur}s)", expanded=True):
                p_col1, p_col2 = st.columns([1, 2])
                with p_col1:
                    st.video(clip["path"])

                with p_col2:
                    c_title = st.text_input("Título:", value=clip.get("title", ""), key=f"title_{idx}")
                    c_caption = st.text_area("Legenda sugerida:", value=clip.get("caption", ""), height=80, key=f"caption_{idx}")

                    act_col1, act_col2 = st.columns(2)
                    with act_col1:
                        target_platform = st.selectbox(
                            "Plataforma Alvo",
                            ["instagram", "tiktok", "youtube_shorts", "instagram_lite", "tiktok_lite"],
                            format_func=lambda x: {
                                "instagram": "Instagram (Oficial)",
                                "tiktok": "TikTok (Oficial)",
                                "youtube_shorts": "YouTube Shorts",
                                "instagram_lite": "Instagram Lite (Legado)",
                                "tiktok_lite": "TikTok Lite (Legado)"
                            }[x],
                            key=f"plat_{idx}"
                        )
                    with act_col2:
                        schedule_choice = st.selectbox(
                            "Quando Postar",
                            ["Agora", "Daqui a 1 hora", "Daqui a 2 horas", "Daqui a 3 horas"],
                            key=f"when_{idx}"
                        )

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if selected_device:
                            if st.button(f"📲 Injetar na Galeria", key=f"push_{idx}", use_container_width=True):
                                if emulator.push_video_to_gallery(selected_device, Path(clip["path"])):
                                    st.success(f"Vídeo enviado para a galeria do {selected_device}!")
                                else:
                                    st.error("Falha ao transferir.")
                    with btn_c2:
                        if selected_device:
                            if st.button(f"📅 Agendar Postagem", key=f"sched_{idx}", type="primary", use_container_width=True):
                                hours_map = {"Agora": 0, "Daqui a 1 hora": 1, "Daqui a 2 horas": 2, "Daqui a 3 horas": 3}
                                sched_time = (datetime.now() + timedelta(hours=hours_map[schedule_choice])).isoformat()
                                db.enqueue_post(
                                    clip_path=clip["path"],
                                    platform=target_platform,
                                    device_serial=selected_device,
                                    title=c_title,
                                    caption=c_caption,
                                    scheduled_at=sched_time
                                )
                                st.success(f"Corte #{clip.get('part', idx+1)} adicionado à Fila de Postagens!")
                        else:
                            st.info("Conecte um emulador para agendar.")

# TAB 2: Fila de Postagens
with tab_queue:
    st.header("📅 Fila de Postagens Automáticas")
    
    q_col1, q_col2 = st.columns([3, 1])
    with q_col2:
        if st.button("⚡ Processar Fila Agora", type="primary", use_container_width=True):
            with st.spinner("Verificando e processando postagens pendentes..."):
                msg = scheduler.process_due_posts_once(force=True)
                st.info(msg)
            st.rerun()

    posts = db.get_all_posts(limit=25)
    if posts:
        for p in posts:
            status_colors = {
                "pending": "🟡 Pendente",
                "processing": "🔵 Postando no Emulador...",
                "completed": "🟢 Publicado",
                "failed": "🔴 Falha"
            }
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**{p['title'] or 'Sem título'}**")
                    st.caption(f"📁 `{Path(p['clip_path']).name}` | 📱 {p['platform']} ({p['device_serial']})")
                    if p.get("error_msg"):
                        st.error(f"Erro: {p['error_msg']}")
                with c2:
                    st.write(status_colors.get(p["status"], p["status"]))
                    st.caption(f"Agendado: {p['scheduled_at'][:16]}")
                with c3:
                    if p["status"] == "completed":
                        current_url = p.get("public_url") or ""
                        new_url = st.text_input("URL Pública do Post:", value=current_url, key=f"url_{p['id']}")
                        if new_url and new_url != current_url:
                            db.update_post_status(p["id"], "completed", public_url=new_url)
                            metrics.refresh_metrics_for_post(p["id"], new_url)
                            st.success("URL salva!")
    else:
        st.info("Nenhuma postagem agendada ou registrada na fila ainda.")

# TAB 3: Dashboard de Métricas
with tab_metrics:
    st.header("📊 Métricas de Performance")
    summary = db.get_metrics_summary()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vídeos Postados", summary.get("total_posts", 0))
    m2.metric("Total de Visualizações", f"{summary.get('total_views', 0):,}")
    m3.metric("Total de Curtidas", f"{summary.get('total_likes', 0):,}")
    m4.metric("Total de Comentários", f"{summary.get('total_comments', 0):,}")

    st.divider()
    st.subheader("Histórico Detalhado dos Posts")
    
    completed_posts = [p for p in db.get_all_posts() if p["status"] == "completed"]
    if completed_posts:
        if st.button("🔄 Atualizar Métricas Públicas"):
            with st.spinner("Atualizando métricas via web..."):
                for p in completed_posts:
                    if p.get("public_url"):
                        metrics.refresh_metrics_for_post(p["id"], p["public_url"])
            st.rerun()

        for p in completed_posts:
            with st.container(border=True):
                st.markdown(f"**{p['title']}** ({p['platform']})")
                if p.get("public_url"):
                    st.caption(f"🔗 [Ver Publicação]({p['public_url']})")
                else:
                    st.caption("Insira a URL pública na aba 'Fila de Postagens' para monitorar visualizações automaticamente.")
    else:
        st.caption("Nenhum post concluído registrado para exibir métricas.")

# TAB 4: Controle de Emuladores
with tab_emulators:
    st.header("📱 Dispositivos e Automação Móvel")
    if devices:
        st.write("Dispositivos detectados via ADB:")
        for dev in devices:
            st.code(dev)

        st.subheader("Ações Rápidas de Teste")
        app_choice = st.selectbox(
            "Aplicativo para Abrir",
            [
                "com.instagram.android (Instagram Oficial)",
                "com.zhiliaoapp.musically (TikTok Oficial)",
                "com.google.android.youtube (YouTube Shorts)",
                "com.instagram.lite (Instagram Lite)",
                "com.zhiliaoapp.musically.go (TikTok Lite)"
            ]
        )
        pkg = app_choice.split(" ")[0]

        if st.button("🚀 Abrir Aplicativo no Emulador"):
            if selected_device:
                emulator.launch_app(selected_device, pkg)
                st.success(f"Comando de abertura enviado para {selected_device}!")
    else:
        st.info("Nenhum emulador ativo. Abra o LDPlayer 9 no Windows.")

# TAB 5: Configurações & Templates
with tab_settings:
    st.header("⚙️ Configurações de Postagem & Templates")
    
    st.subheader("Template de Título e Legenda")
    st.caption("Variáveis disponíveis: `{title}` (Título do corte) e `{caption}` (Legenda sugerida pela IA).")
    
    current_template = config.load_caption_template()
    new_template = st.text_area("Estrutura do Texto:", value=current_template, height=120)
    
    st.subheader("Regras de Frequência de Postagem")
    sched_cfg = config.load_schedule_config()
    
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        posts_per_day = st.slider("Máximo de posts por dia", min_value=1, max_value=5, value=sched_cfg["posts_per_day"])
    with s_col2:
        interval_hours = st.slider("Intervalo mínimo entre posts (horas)", min_value=1.0, max_value=6.0, value=sched_cfg["interval_hours"], step=0.5)

    if st.button("💾 Salvar Configurações e Templates", type="primary"):
        config.save_caption_template(new_template)
        config.save_schedule_config(posts_per_day, interval_hours)
        st.success("Configurações salvas com sucesso!")

    st.divider()
    st.subheader("Pré-visualização do Template Formatado")
    sample_preview = config.format_caption("When the hero reveals his true identity...", "Unbelievable plot twist! #movies #cinema")
    st.code(sample_preview, language="text")
