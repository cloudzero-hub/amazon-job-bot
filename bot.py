import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from datetime import datetime
from scraper import AmazonJobScraper
from config import Config

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
scraper = AmazonJobScraper()

# ─── Startup ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"📡 Monitoring: {Config.JOB_URL}")
    print(f"⏱  Check interval: every {Config.CHECK_INTERVAL_MINUTES} minutes")
    check_for_new_jobs.start()

# ─── Background Task ──────────────────────────────────────────────────────────

@tasks.loop(minutes=Config.CHECK_INTERVAL_MINUTES)
async def check_for_new_jobs():
    channel = bot.get_channel(Config.NOTIFICATION_CHANNEL_ID)
    if not channel:
        print(f"❌ Could not find channel ID {Config.NOTIFICATION_CHANNEL_ID}")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new jobs...")
    try:
        new_jobs = await asyncio.to_thread(scraper.get_new_jobs)
        if new_jobs:
            print(f"  → Found {len(new_jobs)} new job(s)!")
            for job in new_jobs:
                embed = build_job_embed(job)
                await channel.send(embed=embed)
        else:
            print("  → No new jobs found.")
    except Exception as e:
        print(f"  ⚠️  Error during scrape: {e}")

@check_for_new_jobs.before_loop
async def before_check():
    await bot.wait_until_ready()

# ─── Commands ─────────────────────────────────────────────────────────────────

@bot.command(name="jobs")
async def list_jobs(ctx, limit: int = 5):
    """Show the most recent Amazon job listings."""
    await ctx.send("🔍 Fetching latest jobs, please wait...")
    try:
        jobs = await asyncio.to_thread(scraper.fetch_jobs)
        jobs = jobs[:limit]
        if not jobs:
            await ctx.send("😕 No jobs found right now. Try again later.")
            return
        for job in jobs:
            await ctx.send(embed=build_job_embed(job))
    except Exception as e:
        await ctx.send(f"⚠️ Error fetching jobs: {e}")

@bot.command(name="search")
async def search_jobs(ctx, *, keyword: str):
    """Search Amazon jobs by keyword. Usage: !search forklift"""
    await ctx.send(f"🔍 Searching for **{keyword}**...")
    try:
        jobs = await asyncio.to_thread(scraper.fetch_jobs, keyword=keyword)
        if not jobs:
            await ctx.send(f"😕 No jobs found for **{keyword}**.")
            return
        await ctx.send(f"Found **{len(jobs)}** job(s) for **{keyword}**:")
        for job in jobs[:5]:
            await ctx.send(embed=build_job_embed(job))
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

@bot.command(name="setlocation")
async def set_location(ctx, *, location: str):
    """Set a location filter. Usage: !setlocation Moncton"""
    Config.LOCATION_FILTER = location
    await ctx.send(f"📍 Location filter set to: **{location}**")

@bot.command(name="status")
async def status(ctx):
    """Show bot status and current config."""
    seen = scraper.load_seen_ids()
    embed = discord.Embed(title="🤖 Amazon Job Bot Status", color=0x00B2FF)
    embed.add_field(name="Check Interval", value=f"{Config.CHECK_INTERVAL_MINUTES} min", inline=True)
    embed.add_field(name="Jobs Tracked", value=str(len(seen)), inline=True)
    embed.add_field(name="Location Filter", value=Config.LOCATION_FILTER or "Any", inline=True)
    embed.add_field(name="Next Check", value=f"<t:{int(check_for_new_jobs.next_iteration.timestamp())}:R>", inline=True)
    embed.add_field(name="Monitoring URL", value=Config.JOB_URL, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="clearjobs")
@commands.has_permissions(administrator=True)
async def clear_jobs(ctx):
    """Reset tracked job IDs (admin only). Bot will re-notify all current listings."""
    scraper.save_seen_ids(set())
    await ctx.send("🗑️ Cleared job history. All current listings will be notified on next check.")

@bot.command(name="checkjobs")
async def manual_check(ctx):
    """Manually trigger a job check right now."""
    await ctx.send("🔄 Running manual check...")
    channel = ctx.channel
    try:
        new_jobs = await asyncio.to_thread(scraper.get_new_jobs)
        if new_jobs:
            await ctx.send(f"✅ Found **{len(new_jobs)}** new job(s)!")
            for job in new_jobs:
                await channel.send(embed=build_job_embed(job))
        else:
            await ctx.send("✅ No new jobs since last check.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

# ─── Embed Builder ─────────────────────────────────────────────────────────────

def build_job_embed(job: dict) -> discord.Embed:
    embed = discord.Embed(
        title=job.get("title", "Amazon Job"),
        url=job.get("url", Config.JOB_URL),
        description=job.get("description", "")[:300] + ("..." if len(job.get("description", "")) > 300 else ""),
        color=0xFF9900,  # Amazon orange
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url="https://i.imgur.com/1m9Gy7P.png")  # Amazon logo

    if job.get("location"):
        embed.add_field(name="📍 Location", value=job["location"], inline=True)
    if job.get("job_type"):
        embed.add_field(name="⏰ Type", value=job["job_type"], inline=True)
    if job.get("pay"):
        embed.add_field(name="💰 Pay", value=job["pay"], inline=True)
    if job.get("shift"):
        embed.add_field(name="🔄 Shift", value=job["shift"], inline=True)
    if job.get("posted_date"):
        embed.add_field(name="📅 Posted", value=job["posted_date"], inline=True)

    embed.set_footer(text="Amazon Jobs • hiring.amazon.ca")
    return embed

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not Config.DISCORD_TOKEN:
        raise ValueError("❌ DISCORD_TOKEN not set in .env file!")
    if not Config.NOTIFICATION_CHANNEL_ID:
        raise ValueError("❌ NOTIFICATION_CHANNEL_ID not set in .env file!")
    bot.run(Config.DISCORD_TOKEN)
