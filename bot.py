import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp
from threading import Thread
from flask import Flask

# --- KEEP-ALIVE SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "✅ Luan Music Bot is running on Render!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_web).start()
# -------------------------------------

# show more info in console
logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# On Render, ffmpeg is installed globally
FFMPEG_PATH = "ffmpeg"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- GLOBAL QUEUE STORAGE ---
queues = {}  # {guild_id: [urls]}

# --- YTDL CONFIG ---
yt_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "extract_flat": "in_playlist",
    "cookiefile": "cookies.txt"
}

ytdl = yt_dlp.YoutubeDL(yt_opts)

def get_queue(ctx):
    return queues.setdefault(ctx.guild.id, [])

async def join_channel(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
    else:
        await ctx.send("❗ Join a voice channel first!")

async def play_next(ctx):
    vc = ctx.voice_client
    queue = get_queue(ctx)

    if not queue:
        # no more songs -> optional: disconnect after 10s
        await asyncio.sleep(10)
        if not get_queue(ctx):
            await vc.disconnect()
        return

    url = queue.pop(0)
    info = ytdl.extract_info(url, download=False)
    audio_url = info["url"]
    title = info.get("title")

    source = await discord.FFmpegOpusAudio.from_probe(
        audio_url,
        method="fallback",
        executable=FFMPEG_PATH
    )

    vc.play(
        source,
        after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
    )

    await ctx.send(f"▶️ Now playing: **{title}**")

# ----------------- COMMANDS -----------------

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command(help="Play a YouTube or SoundCloud link, or search query")
async def play(ctx, *, query: str):
    if not ctx.author.voice:
        return await ctx.send("❗ Join a voice channel first!")
    await join_channel(ctx)
    queue = get_queue(ctx)

    info = ytdl.extract_info(query, download=False)
    if "entries" in info:
        info = info["entries"][0]
    url = info["webpage_url"]
    title = info["title"]
    queue.append(url)

    await ctx.send(f"🎵 Added to queue: **{title}**")

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

@bot.command(help="Pause the current song")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused.")

@bot.command(help="Resume playback")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed.")

@bot.command(help="Skip to the next song")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped.")

@bot.command(help="Show songs in queue")
async def queue(ctx):
    q = get_queue(ctx)
    if not q:
        await ctx.send("🚫 Queue is empty.")
    else:
        msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(q)])
        await ctx.send(f"🎶 **Queue:**\n{msg}")

@bot.command(help="Stop music and clear queue")
async def stop(ctx):
    q = get_queue(ctx)
    q.clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    await ctx.send("🛑 Stopped and cleared queue.")

bot.run(TOKEN)
