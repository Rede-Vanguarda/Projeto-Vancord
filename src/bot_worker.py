import discord
from discord.ext import commands
import subprocess
import json
import argparse
import sys
import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler

import nacl
import nacl.secret
import nacl.utils
import nacl.signing
import nacl.public

def setup_logger(nome_bot):
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger(nome_bot)
    logger.setLevel(logging.INFO)
    
    file_name = nome_bot.replace(" ", "_").replace("í", "i").lower()
    handler = RotatingFileHandler(
        f"logs/{file_name}_worker.log", 
        maxBytes=5*1024*1024, 
        backupCount=3, 
        encoding='utf-8'
    )
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(stream_handler)
    return logger

def carregar_settings():
    try:
        with open("settings.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar settings.json: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Bot Worker para gerenciar Híbridas.")
    parser.add_argument("--bot", type=str, required=True, help="Nome do bot conforme no settings.json")
    args = parser.parse_args()

    nome_mapeado = args.bot
    settings = carregar_settings()
    
    if "bots" not in settings or nome_mapeado not in settings["bots"]:
        print(f"Erro: Bot '{nome_mapeado}' não configurado em settings.json")
        sys.exit(1)
        
    config = settings["bots"][nome_mapeado]
    token = config["token"]
    nome_exibicao = config["nome_exibicao"]
    canal_voz_id = config["canal_voz_id"]
    canal_texto_id = config["canal_texto_id"]
    microfone = config["microfone"]
    ffmpeg_args_extras = config.get("ffmpeg_args", [])

    logger = setup_logger(nome_mapeado)
    logger.info(f"Iniciando {nome_mapeado} ({nome_exibicao})")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.voice_states = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    async def conectar_e_transmitir(guild: discord.Guild):
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_channel = guild.get_channel(canal_voz_id)
        if not voice_channel:
            msg = f"Canal de voz {canal_voz_id} não encontrado."
            logger.error(msg)
            return False, msg

        try:
            logger.info(f"Conectando à {voice_channel.name}...")
            # Tentativa de estabilização do connection handshake do discord.py
            vc = await voice_channel.connect(reconnect=True, timeout=30.0)
            logger.info(f"Microfone selecionado: '{microfone}'")

            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'dshow',
                '-rtbufsize', '512M',
                '-i', f'audio={microfone}',
                '-ac', '2',
                '-f', 's16le',
                '-ar', '48000',
            ]
            ffmpeg_cmd.extend(ffmpeg_args_extras)
            ffmpeg_cmd.append('pipe:1')

            logger.info(f"Iniciando FFMPEG: {' '.join(ffmpeg_cmd)}")
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            source = discord.PCMAudio(process.stdout)
            vc.play(source)

            msg = f"[VOZ] {nome_exibicao} conectada e transmitindo em '{voice_channel.name}'!"
            logger.info(msg)
            return True, None
        except Exception as e:
            msg = f"[ERRO] Falha ao conectar: {e}"
            logger.error(msg)
            if guild.voice_client:
                await guild.voice_client.disconnect(force=True)
            return False, msg

    class BotaoConectar(discord.ui.Button):
        def __init__(self):
            super().__init__(label=f"Conectar {nome_exibicao}", style=discord.ButtonStyle.success)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            success, error_msg = await conectar_e_transmitir(interaction.guild)
            if success:
                voice_channel = interaction.guild.get_channel(canal_voz_id)
                await interaction.followup.send(f"🔊 {nome_exibicao} conectada em **{voice_channel.name}**!", ephemeral=True)
            else:
                await interaction.followup.send(error_msg, ephemeral=True)

    class BotaoDesconectar(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Desconectar", style=discord.ButtonStyle.danger)

        async def callback(self, interaction: discord.Interaction):
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect(force=True)
                await interaction.response.send_message("⏹️ Desconectado do canal de voz.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ O bot não está em nenhum canal de voz.", ephemeral=True)

    class ViewBotoes(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(BotaoConectar())
            self.add_item(BotaoDesconectar())

    @bot.event
    async def on_ready():
        if getattr(bot, '_setup_complete', False):
            logger.info(f"Reconexão do websocket detectada ({bot.user}). Startup ignorado.")
            return
            
        bot._setup_complete = True
        logger.info(f"{bot.user} está online e o websocket está conectado.")
        canal_texto = bot.get_channel(canal_texto_id)
        if not canal_texto:
            logger.error(f"Canal de texto {canal_texto_id} não encontrado.")
            return

        try:
            async for msg in canal_texto.history(limit=100):
                if msg.author == bot.user:
                    await msg.delete()
        except Exception as e:
            logger.warning(f"Não foi possível limpar mensagens: {e}")

        logger.info(f"Enviando painel para o canal...")
        await canal_texto.send(f"Painel da híbrida '{nome_exibicao}'", view=ViewBotoes())

        logger.info("Tentando conexao automatica ao iniciar...")
        if canal_texto.guild:
            await conectar_e_transmitir(canal_texto.guild)
        else:
            logger.error("Guild não encontrada a partir do canal_texto.")

    @bot.event
    async def on_voice_state_update(member, before, after):
        # Desconexão indesejada detectada
        if member.id == bot.user.id:
            if before.channel is not None and after.channel is None:
                logger.warning("Bot foi desconectado do canal de voz inadvertidamente!")

    try:
        # Reconnect logic interna do discord.py ativada
        bot.run(token, reconnect=True)
    except discord.errors.LoginFailure as e:
        logger.critical(f"Falha de Login (Token inválido?): {e}")
    except Exception as e:
        logger.critical(f"Erro fatal executando bot: {e}")

if __name__ == "__main__":
    main()
