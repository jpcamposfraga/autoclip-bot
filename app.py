import streamlit as st
import time
from datetime import datetime
from pathlib import Path
import config
from config import CLIPS_DIR
import clipper
import db
import telegram_bot
import email_sender
import live_orchestrator

st.set_page_config(
    page_title="AutoClip GTA 6 Factory",
    page_icon="🎬",
    layout="wide"
)

# Initialize Session State
if "gemini_key" not in st.session_state:
    st.session_state["gemini_key"] = config.load_gemini_key()
if "generated_clips" not in st.session_state:
    st.session_state["generated_clips"] = []

# Sidebar
with st.sidebar:
    st.title("🎬 GTA 6 Clipper Factory")
    st.caption("Sistema autônomo de cortes ao vivo para TikTok, Shorts e Reels.")

    # 1. Gemini Keys Pool (Plano A + Plano B)
    st.subheader("🧠 Chaves Gemini (Plano A + B)")
    current_keys = config.load_gemini_keys_pool()
    key_1 = current_keys[0] if len(current_keys) > 0 else ""
    key_2 = current_keys[1] if len(current_keys) > 1 else ""

    key_1_input = st.text_input("Chave Principal (Plano A)", value=key_1, type="password", help="Chave gratuita do Google AI Studio")
    key_2_input = st.text_input("Chave Reserva (Plano B)", value=key_2, type="password", help="Chave secundária de outra conta Google para fallback automático")

    new_keys = [k.strip() for k in [key_1_input, key_2_input] if k.strip()]
    if new_keys != current_keys and (key_1_input or key_2_input):
        config.save_gemini_keys_pool(new_keys)
        st.session_state["gemini_key"] = new_keys[0] if new_keys else ""
        st.toast("Chaves de IA salvas com sucesso!", icon="💾")

    st.divider()

    # 2. Telegram Status
    st.subheader("📱 Status Telegram")
    tg_cfg = config.load_telegram_config()
    chat_ids = telegram_bot.parse_chat_ids(tg_cfg.get("chat_id", ""))
    if tg_cfg.get("bot_token") and chat_ids:
        st.success(f"🟢 Conectado ({len(chat_ids)} destinatário(s))")
    else:
        st.warning("⚠️ Configure o Bot na aba Configurações")

    st.divider()

    # 3. Auto-Refresh Toggle
    st.subheader("🔄 Telemetria da Tela")
    auto_refresh = st.toggle("Atualizar tela em tempo real (2s)", value=False, help="Atualiza espectadores e velocidades de chat automaticamente")

# Main Application Tabs: Exactly 3 focused tabs
tab_lives, tab_manual, tab_settings = st.tabs([
    "🔴 Multi-Live GTA 6 (3 Slots)",
    "🎬 Clipar Link/VOD (Manual)",
    "⚙️ Configurações & Telegram"
])

# TAB 1: Multi-Live GTA 6
with tab_lives:
    st.subheader("📡 Monitoramento Multi-Live Simultâneo (Até 3 Transmissões)")
    st.caption(
        "A IA monitora até 3 lives em paralelo mantendo buffers circulares de 150 segundos. "
        "Quando o chat explode proporcionalmente ao número de espectadores, corta automaticamente de 61s a 75s "
        "(qualificado para monetização do TikTok) e dispara instantaneamente para o seu Telegram e do seu amigo!"
    )

    all_statuses = live_orchestrator.get_all_sessions_status()
    any_active = any(s["active"] for s in all_statuses)

    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]

    for idx, col in enumerate(cols):
        session_id = idx + 1
        s_data = all_statuses[idx]
        is_active = s_data["active"]

        with col:
            with st.container(border=True):
                st.markdown(f"### 🎮 Live Slot #{session_id}")
                
                stream_url = st.text_input(
                    f"URL da Live #{session_id}",
                    placeholder="https://www.youtube.com/watch?v=... ou Twitch",
                    value=s_data["stream_url"] if is_active else "",
                    disabled=is_active,
                    key=f"url_slot_{session_id}"
                )

                # Status Metrics
                m_c1, m_c2 = st.columns(2)
                with m_c1:
                    st.metric("Status", "🟢 Ao Vivo" if is_active else "⚪ Inativo")
                    st.metric("Espectadores", f"👥 {s_data['viewers']:,}" if s_data['viewers'] > 0 else "👥 --")
                with m_c2:
                    st.metric("Velocidade Chat", f"💬 {s_data['current_mps']:.1f} m/s")
                    st.metric("Gatilho Exigido", f"🎯 > {s_data['required_mps']:.1f} m/s" if is_active else "🎯 --")

                if s_data.get("error_message"):
                    st.warning(f"⚠️ {s_data['error_message']}")

                # Control Buttons
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if not is_active:
                        if st.button(f"▶️ Iniciar #{session_id}", key=f"btn_start_{session_id}", type="primary", use_container_width=True):
                            if not stream_url:
                                st.error("Insira uma URL de live válida.")
                            elif not config.load_gemini_keys_pool():
                                st.error("Configure ao menos uma Gemini API Key na barra lateral.")
                            else:
                                with st.spinner(f"Iniciando buffer e chat da Live #{session_id}..."):
                                    ok, msg = live_orchestrator.start_live_session(stream_url, session_id=session_id)
                                    if ok:
                                        st.success(msg)
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                    else:
                        if st.button(f"⏹️ Parar #{session_id}", key=f"btn_stop_{session_id}", type="secondary", use_container_width=True):
                            live_orchestrator.stop_live_session(session_id)
                            st.info(f"Live #{session_id} parada.")
                            time.sleep(1)
                            st.rerun()

                with b_col2:
                    if is_active:
                        if st.button(f"⚡ Clipar 65s", key=f"btn_manual_{session_id}", help="Corta os últimos 65s do buffer agora mesmo e envia pro Telegram", use_container_width=True):
                            ok, msg = live_orchestrator.trigger_manual_live_clip(session_id)
                            if ok:
                                st.toast(f"Corte manual disparado para Live #{session_id}!", icon="🎬")
                                st.info("Processando os últimos 65s da live... Chegará no Telegram em breve!")
                            else:
                                st.error(msg)
                    else:
                        st.caption("Disponível quando ativo")

                if is_active and s_data["last_clip_title"]:
                    st.caption(f"Último corte: **{s_data['last_clip_title']}** (Total: {s_data['clips_count']})")

    st.divider()

    # Galeria de Cortes Gerados
    st.subheader("🎬 Galeria de Cortes Recentes de GTA 6")
    live_clips_on_disk = sorted(
        list(CLIPS_DIR.glob("live_gta6_*_vertical.mp4")),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if live_clips_on_disk:
        for idx, clip_file in enumerate(live_clips_on_disk[:6]):
            with st.container(border=True):
                col_vid, col_info = st.columns([1, 2])
                with col_vid:
                    st.video(str(clip_file))
                with col_info:
                    c_title = clip_file.stem.replace("_vertical", "").replace("live_gta6_", "Corte ")
                    st.markdown(f"**🎬 {c_title}**")
                    c_caption = config.format_caption(c_title, "#GTA6 #GTA #Viral #Gaming #Shorts")
                    st.text_area("Legenda gerada:", value=c_caption, height=75, key=f"feed_cap_{idx}")

                    ac1, ac2 = st.columns(2)
                    with ac1:
                        if st.button("💬 Reenviar no Telegram", key=f"feed_tg_{idx}", type="primary", use_container_width=True):
                            with st.spinner("Enviando vídeo para o Telegram..."):
                                ok = telegram_bot.send_clip_to_telegram(str(clip_file), c_caption)
                                if ok:
                                    st.success("Vídeo entregue no Telegram de todos os destinatários!")
                                else:
                                    st.error("Falha ao entregar no Telegram.")
                    with ac2:
                        if st.button("📧 Reenviar por E-mail", key=f"feed_em_{idx}", use_container_width=True):
                            with st.spinner("Enviando e-mail..."):
                                ok, msg = email_sender.send_clip_by_email(str(clip_file), c_title, c_caption)
                                if ok:
                                    st.success(msg)
                                else:
                                    st.error(msg)
    else:
        st.info("Nenhum corte de live gerado ainda. Inicie o monitoramento em um dos slots acima!")

# TAB 2: Clipar Link/VOD Manual
with tab_manual:
    st.subheader("🎬 Criar Cortes Verticais a partir de Link do YouTube")
    st.caption("Cole o link de uma cena ou gameplay para a IA identificar os melhores momentos, renderizar em 9:16 e enviar imediatamente no Telegram.")

    yt_url = st.text_input("URL do Vídeo no YouTube", placeholder="https://www.youtube.com/watch?v=...")
    m_col1, m_col2 = st.columns([1, 1])
    with m_col1:
        max_clips = st.slider("Quantidade de cortes a extrair", min_value=1, max_value=5, value=2)
    with m_col2:
        st.write("")
        auto_send_telegram = st.checkbox("💬 Enviar no Telegram assim que cada corte for gerado", value=True)
        start_btn = st.button("⚡ Processar e Gerar Cortes 9:16", type="primary", use_container_width=True)

    if start_btn:
        if not yt_url:
            st.error("Insira uma URL válida do YouTube.")
        elif not config.load_gemini_keys_pool():
            st.error("Configure sua Gemini API Key na barra lateral.")
        else:
            status_box = st.status("Iniciando pipeline de corte...", expanded=True)
            try:
                status_box.update(label="1/4 Baixando vídeo...")
                video_id = f"clip_{int(time.time())}"
                video_path = clipper.download_youtube(yt_url, video_id=video_id)

                status_box.update(label="2/4 Extraindo áudio para análise...")
                audio_path = clipper.extract_audio(video_path)

                status_box.update(label="3/4 IA identificando ganchos virais e legendas...")
                clips_data = clipper.analyze_scene_with_gemini(
                    audio_path,
                    max_clips=max_clips,
                    status_callback=lambda msg: status_box.update(label=f"3/4 {msg}")
                )

                if not clips_data:
                    raise RuntimeError("Nenhum segmento viral válido foi identificado no áudio fornecido.")

                def _on_clip_done(clip_item):
                    if auto_send_telegram:
                        caption = config.format_caption(clip_item.get("title", ""), clip_item.get("caption", ""))
                        telegram_bot.send_clip_to_telegram(clip_item["path"], caption)
                        st.toast(f"Corte #{clip_item.get('part')} entregue no Telegram!", icon="🚀")

                status_box.update(label=f"4/4 Renderizando {len(clips_data)} corte(s) em 9:16...")
                rendered_clips = clipper.render_clips_batch(
                    video_path=video_path,
                    clips_data=clips_data,
                    video_id=video_id,
                    status_callback=lambda msg: status_box.update(label=f"4/4 {msg}"),
                    on_clip_rendered_callback=_on_clip_done
                )

                st.session_state["generated_clips"] = rendered_clips
                status_box.update(label=f"✅ {len(rendered_clips)} corte(s) concluído(s) e enviados com sucesso!", state="complete")
            except Exception as e:
                status_box.update(label=f"❌ Erro durante o processamento: {e}", state="error")
                st.exception(e)

# TAB 3: Configurações & Telegram
with tab_settings:
    st.header("⚙️ Configurações & Canais de Entrega")

    # 1. Telegram Multi-Destinatários
    st.subheader("📱 Entrega via Telegram (Você + Amigo)")
    st.caption("Receba os cortes renderizados em tempo real no seu smartphone e de mais pessoas.")

    with st.expander("💡 Como configurar para 2 ou mais celulares (Passo a Passo)", expanded=False):
        st.markdown("""
1. **Criar o Bot (se ainda não tiver):**
   - No Telegram, busque por `@BotFather` e envie `/newbot`.
   - Copie o **Token HTTP API** e cole abaixo.
2. **PASSO CRÍTICO: Clicar em /start no Bot:**
   - **Você** deve abrir a conversa com seu bot no Telegram e clicar em **/start**.
   - **A outra pessoa** também DEVE abrir a conversa com o mesmo bot e clicar em **/start**.
3. **Descobrir o Chat ID de cada um:**
   - Cada um deve mandar um "Oi" para o bot `@userinfobot` no Telegram para ver seu número de `Id`.
4. **Inserir os IDs:**
   - Digite os dois números separados por vírgula no campo abaixo (ex: `123456789, 987654321`).
        """)

    tg_cfg = config.load_telegram_config()
    tg_col1, tg_col2 = st.columns(2)
    with tg_col1:
        bot_token_input = st.text_input("Telegram Bot Token", value=tg_cfg["bot_token"], type="password", help="Token fornecido pelo @BotFather")
    with tg_col2:
        chat_id_input = st.text_input(
            "Chat IDs (separados por vírgula)",
            value=tg_cfg["chat_id"],
            help="Ex: 123456789, 987654321 (insira o seu ID e o da outra pessoa)"
        )

    if st.button("🔔 Testar Conexão com Telegram"):
        if not bot_token_input or not chat_id_input:
            st.error("Preencha o Token e pelo menos um Chat ID antes de testar.")
        else:
            with st.spinner("Enviando mensagem de teste para todos os destinatários..."):
                ok, msg = telegram_bot.test_telegram_connection(bot_token_input, chat_id_input)
                if ok:
                    config.save_telegram_config(bot_token_input, chat_id_input)
                    st.success(msg)
                else:
                    st.error(msg)

    st.divider()

    # 2. Estratégia de Duração (Monetização x Tração)
    st.subheader("💰 Estratégia de Duração dos Cortes")
    st.caption("O TikTok Creator Rewards exige vídeos com mais de 1 minuto (>=61s) para monetizar.")
    
    current_dur_mode = config.load_duration_mode()
    dur_options = ["hybrid", "monetization", "traction"]
    dur_index = dur_options.index(current_dur_mode) if current_dur_mode in dur_options else 0
    
    dur_choice = st.radio(
        "Selecione o modo de duração dos clipes gerados:",
        options=dur_options,
        index=dur_index,
        format_func=lambda x: {
            "hybrid": "🎯 Híbrido Inteligente (70% Monetização >=61s / 30% Tração Rápida 35s) [Recomendado]",
            "monetization": "💰 Apenas Monetização (Todos os vídeos com 61s a 75s para monetizar no TikTok)",
            "traction": "⚡ Apenas Tração Rápida (Todos os vídeos com 30s a 45s para viralizar rápido)"
        }[x]
    )

    st.divider()

    # 3. E-mail Opcional
    st.subheader("📧 Entrega Secundária via E-mail (Opcional)")
    email_cfg = config.load_email_config()
    em_c1, em_c2 = st.columns(2)
    with em_c1:
        sender_email_input = st.text_input("E-mail Remetente", value=email_cfg.get("sender_email", ""))
        sender_pwd_input = st.text_input("Senha de App (16 letras)", value=email_cfg.get("sender_password", ""), type="password")
    with em_c2:
        recipient_email_input = st.text_input("E-mail de Destino", value=email_cfg.get("recipient_email", ""))
        smtp_server_input = st.text_input("Servidor SMTP", value=email_cfg.get("smtp_server", "smtp.gmail.com"))

    st.divider()

    # 4. Template de Legenda
    st.subheader("Template de Título e Legenda")
    current_template = config.load_caption_template()
    new_template = st.text_area("Estrutura do Texto:", value=current_template, height=100)

    if st.button("💾 Salvar Todas as Configurações", type="primary", use_container_width=True):
        config.save_telegram_config(bot_token_input, chat_id_input)
        config.save_duration_mode(dur_choice)
        config.save_email_config(sender_email_input, sender_pwd_input, recipient_email_input, smtp_server_input)
        config.save_caption_template(new_template)
        st.success("Configurações salvas e aplicadas com sucesso!")

# Auto-Refresh Loop
if auto_refresh and any_active:
    time.sleep(2)
    st.rerun()
