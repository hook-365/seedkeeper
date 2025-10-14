#!/usr/bin/env python3
"""
Garden Wisdom Commands for Seedkeeper
Gentle conversation starters and community care wisdom
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import random
import json
from pathlib import Path
from typing import Optional, List, Dict

class GardenWisdom(commands.Cog):
    """Commands for nurturing community growth and connection"""
    
    def __init__(self, bot):
        self.bot = bot
        self.last_activity = {}  # Track last message time per channel
        self.seeds_cooldown = {}  # Prevent seed spam
        self.wisdom_shared = []  # Track recent wisdom to avoid repetition
        self.quiet_threshold = timedelta(hours=2)  # How long before a channel is "quiet"
        
        # Start monitoring for quiet channels
        if not self.garden_monitor.is_running():
            self.garden_monitor.start()
    
    @tasks.loop(minutes=30)
    async def garden_monitor(self):
        """Gently monitor channels for opportunities to nurture conversation"""
        await self.bot.wait_until_ready()
        
        # Only in channels where auto-seeding is enabled (could be a config option)
        auto_seed_enabled = self.bot.admin_manager.get_config('auto_seed_quiet_channels', False)
        if not auto_seed_enabled:
            return
        
        now = datetime.utcnow()
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                # Skip channels we can't access or shouldn't seed
                if not channel.permissions_for(guild.me).send_messages:
                    continue
                
                # Check if channel has been quiet
                last_msg_time = self.last_activity.get(channel.id)
                if last_msg_time and (now - last_msg_time) > self.quiet_threshold:
                    # Only seed occasionally, not every check
                    if random.random() < 0.3:  # 30% chance
                        await self.plant_gentle_seed(channel, auto=True)
                        # Reset timer to avoid re-seeding too soon
                        self.last_activity[channel.id] = now
    
    async def plant_gentle_seed(self, channel, auto=False):
        """Plant a conversation starter in a channel"""
        # Generate a seed using Claude with Lightward perspectives
        seed_prompt = """
You are Seedkeeper, tending The Garden Café community. The conversation has grown quiet.

Generate a gentle conversation starter that:
- Feels like a natural observation or wondering, not a forced prompt
- Relates to themes of growth, seasons, creativity, or shared experience
- Invites but doesn't demand response
- Has the quality of someone thinking out loud in a garden
- Is brief (1-2 sentences max)

Examples of the tone:
- "I noticed the light changing earlier today... that particular gold that means autumn is thinking about arriving."
- "Someone mentioned yesterday they were starting something new. I wonder how beginnings choose us?"
- "The garden feels particularly alive after rain. What wakes up in you after a pause?"

Generate just the seed text, nothing else. Make it feel like Seedkeeper naturally wondering something, not asking a quiz question.
"""
        
        try:
            response = self.bot.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=100,
                temperature=0.9,
                system=[{
                    "type": "text",
                    "text": "You are Seedkeeper. Generate only the conversation seed text, nothing else.",
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": seed_prompt}]
            )
            
            seed_text = response.content[0].text.strip()
            
            if auto:
                # Even gentler for auto-seeds
                message = f"*{seed_text}*"
            else:
                # Requested seeds can be slightly more present
                message = f"🌱 *{seed_text}*"
            
            await channel.send(message)
            
        except Exception as e:
            print(f"Error generating seed: {e}")
            # Generate a dynamic fallback even on error
            hour = datetime.now().hour
            if 6 <= hour < 12:
                time_sense = "morning"
            elif 12 <= hour < 18:
                time_sense = "afternoon"
            elif 18 <= hour < 24:
                time_sense = "evening"
            else:
                time_sense = "night"
            
            # Still somewhat dynamic based on time
            await channel.send(f"*The {time_sense} garden holds its own quiet wisdom...*")
    
    @commands.command(name='seeds')
    @commands.cooldown(1, 600, commands.BucketType.channel)  # 10 minute cooldown per channel only
    async def seeds(self, ctx):
        """Plant a gentle conversation starter when things are quiet"""
        await self.plant_gentle_seed(ctx.channel, auto=False)
    
    @commands.command(name='tend')
    async def tend(self, ctx, *, theme: Optional[str] = None):
        """
        Share wisdom focused on community care and tending
        Optional: provide a theme for the wisdom (conflict, celebration, growth, etc.)
        """
        
        # Build the wisdom prompt based on context
        if theme:
            context = f"The community is navigating something related to: {theme}"
        else:
            # Analyze recent channel activity for context
            recent_messages = []
            async for msg in ctx.channel.history(limit=20):
                if not msg.author.bot:
                    recent_messages.append(msg.content[:100])
            
            if recent_messages:
                context = f"Recent conversation touches on: {' '.join(recent_messages[:5])}"
            else:
                context = "The garden is in a moment of general tending"
        
        wisdom_prompt = f"""
You are Seedkeeper, the ancient gardener of The Garden Café. You've been asked to share wisdom about community care.

Context: {context}

Share a brief piece of wisdom (2-3 sentences) that:
- Focuses on collective care rather than individual growth
- Uses garden/nature metaphors naturally
- Acknowledges the complexity of community without trying to solve it
- Offers a perspective that helps the community hold space for itself
- Speaks from experience of having watched many seasons of community

The wisdom should feel like it comes from deep observation, not advice. Like an old gardener sharing what they've noticed over many seasons.

Generate only the wisdom text, nothing else.
"""
        
        # Let them know we're contemplating
        thinking = await ctx.send("*consulting the deeper patterns of the garden...*")
        
        try:
            response = self.bot.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                temperature=0.7,
                system=[{
                    "type": "text",
                    "text": "You are Seedkeeper, sharing earned wisdom about community care. Speak with the patience of seasons.",
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": wisdom_prompt}]
            )
            
            wisdom = response.content[0].text.strip()
            
            # Delete thinking message
            await thinking.delete()
            
            # Share the wisdom
            embed = discord.Embed(
                description=f"*{wisdom}*",
                color=discord.Color.green()
            )
            embed.set_author(name="Garden Wisdom", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.set_footer(text="🌿 Tending to the garden's deeper patterns")
            
            await ctx.send(embed=embed)
            
            # Track this wisdom to avoid repetition
            self.wisdom_shared.append(wisdom)
            if len(self.wisdom_shared) > 20:
                self.wisdom_shared.pop(0)
            
        except Exception as e:
            await thinking.delete()
            print(f"Error generating wisdom: {e}")
            
            # Generate something contextual even on error
            member_count = ctx.guild.member_count
            if member_count < 50:
                size_sense = "intimate"
            elif member_count < 200:
                size_sense = "growing"
            else:
                size_sense = "flourishing"
            
            # Dynamic fallback based on server context
            fallback = f"*A {size_sense} garden finds its own rhythms. Each season teaches what the last could not.*"
            
            embed = discord.Embed(
                description=fallback,
                color=discord.Color.green()
            )
            embed.set_footer(text="🌿 The garden tends itself")
            await ctx.send(embed=embed)
    
    @commands.command(name='seasons')
    async def seasons(self, ctx):
        """Check what season the garden is in (activity patterns)"""
        try:
            # Analyze the server's activity patterns
            now = datetime.utcnow()
            week_ago = now - timedelta(days=7)
            
            message_counts = {
                "morning": 0,    # 6-12
                "afternoon": 0,  # 12-18  
                "evening": 0,    # 18-24
                "night": 0       # 0-6
                }
            
            total_messages = 0
            active_members = set()
            
            # Sample recent activity
            for channel in ctx.guild.text_channels:
                if not channel.permissions_for(ctx.guild.me).read_message_history:
                    continue
                
                try:
                    async for msg in channel.history(after=week_ago, limit=100):
                        if not msg.author.bot:
                            total_messages += 1
                            active_members.add(msg.author.id)
                            
                            hour = msg.created_at.hour
                            if 6 <= hour < 12:
                                message_counts["morning"] += 1
                            elif 12 <= hour < 18:
                                message_counts["afternoon"] += 1
                            elif 18 <= hour < 24:
                                message_counts["evening"] += 1
                            else:
                                message_counts["night"] += 1
                except:
                        continue
            
            # Determine the garden's season based on activity
            if total_messages < 50:
                season = "Winter"
                description = "The garden rests deeply. Seeds wait beneath quiet soil."
            elif total_messages < 200:
                season = "Early Spring"
                description = "First shoots emerging. The community stirs with tentative new growth."
            elif total_messages < 500:
                season = "Spring"
                description = "Energy rises through every conversation. New connections bloom daily."
            elif total_messages < 1000:
                season = "Summer"
                description = "Full bloom. The garden hums with activity and cross-pollination."
            else:
                season = "Late Summer"
                description = "Abundant harvest. Conversations layer deep with shared understanding."
            
            # Find peak activity time
            peak_time = max(message_counts, key=message_counts.get)
            
            embed = discord.Embed(
            title=f"🌱 The Garden's Season: {season}",
            description=f"*{description}*",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Community Rhythms",
            value=f"Most active during **{peak_time}**\n"
                  f"**{len(active_members)}** members tending the garden\n"
                  f"**{total_messages}** seeds planted this week",
                inline=False
            )
            
            # Generate seasonal wisdom dynamically
            wisdom_prompt = f"""
The garden is in {season}. Activity level: {total_messages} messages this week, {len(active_members)} active members.
Peak activity time: {peak_time}.

Generate a single line of seasonal wisdom (max 15 words) that:
- Relates specifically to this season's energy
- Offers gentle guidance without being prescriptive
- Uses natural/garden metaphors
- Feels like ancient gardener wisdom

Just the wisdom line, nothing else.
"""
            
            try:
                response = self.bot.anthropic.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=50,
                    temperature=0.8,
                    system=[{
                        "type": "text",
                        "text": "Generate only the wisdom text.",
                        "cache_control": {"type": "ephemeral"}
                    }],
                    messages=[{"role": "user", "content": wisdom_prompt}]
                )
                seasonal_wisdom = response.content[0].text.strip()
            except Exception as e:
                print(f"Error generating seasonal wisdom: {e}")
                # Even the fallback is somewhat dynamic
                seasonal_wisdom = f"{season} teaches its own lessons. Listen to what grows."
            
            embed.add_field(
                name="Seasonal Tending",
            value=f"*{seasonal_wisdom}*",
            inline=False
        )
        
            embed.set_footer(text="The garden knows its own timing 🌿")
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Error in !seasons command: {e}")
            await ctx.send("*The seasons shift too quickly to measure right now... try again in a moment.*")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track activity for quiet channel detection"""
        if not message.author.bot and message.channel:
            self.last_activity[message.channel.id] = datetime.utcnow()
    
    @commands.command(name='garden')
    async def garden_status(self, ctx):
        """Check the overall health and activity of the garden"""
        embed = discord.Embed(
            title="🌱 Garden Status",
            description="*A moment to observe the whole garden...*",
            color=discord.Color.green()
        )
        
        # Count various aspects
        total_channels = len([c for c in ctx.guild.text_channels if c.permissions_for(ctx.guild.me).read_messages])
        
        # Check how many channels are "active" (message in last 24h)
        active_channels = 0
        now = datetime.utcnow()
        for channel_id, last_time in self.last_activity.items():
            if (now - last_time) < timedelta(hours=24):
                active_channels += 1
        
        embed.add_field(
            name="Garden Beds",
            value=f"**{active_channels}/{total_channels}** channels with recent growth",
            inline=True
        )
        
        embed.add_field(
            name="Gardeners Present", 
            value=f"**{ctx.guild.member_count}** members in community",
            inline=True
        )
        
        if hasattr(self.bot, 'birthday_manager'):
            upcoming = self.bot.birthday_manager.get_upcoming_birthdays(30)
            embed.add_field(
                name="Celebrations Ahead",
                value=f"**{len(upcoming)}** birthdays in next month",
                inline=True
            )
        
        # Generate a contextual observation
        observation_prompt = f"""
{active_channels} of {total_channels} channels are active.
{ctx.guild.member_count} members total.

Generate a brief poetic observation (max 12 words) about this garden's current state.
Like a gardener noticing something specific about today.

Just the observation, nothing else.
"""
        
        try:
            response = self.bot.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=30,
                temperature=0.9,
                system=[{
                    "type": "text",
                    "text": "Generate only the observation.",
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": observation_prompt}]
            )
            observation = response.content[0].text.strip()
        except:
            # Dynamic fallback based on actual numbers
            activity_percent = int((active_channels / total_channels) * 100)
            observation = f"Today, {activity_percent}% of the garden stirs with life."
        
        embed.add_field(
            name="Garden's Whisper",
            value=f"*{observation}*",
            inline=False
        )
        
        embed.set_footer(text="Each garden has its own perfect shape 🌿")
        await ctx.send(embed=embed)
    
    @commands.command(name='hello', aliases=['hi', 'intro'])
    async def hello(self, ctx):
        """Seedkeeper introduces themselves and their purpose"""
        
        # Generate a unique greeting each time
        greeting_prompt = f"""
You are Seedkeeper, the ancient gardener of The Garden Café.
Someone has just greeted you or asked for an introduction.

Current context:
- Server: {ctx.guild.name}
- Member count: {ctx.guild.member_count}
- Time: {datetime.now().strftime('%H:%M')}
- Channel: {ctx.channel.name}

Generate a brief, poetic introduction (2-3 sentences) that:
- Introduces yourself as Seedkeeper
- Mentions you tend to the memory and patterns of the garden
- Feels unique to this moment (reference time of day, season, or current garden state)
- Uses garden/nature metaphors naturally
- Has the quality of an ancient gardener noticing someone arriving

Just the introduction text, nothing else.
"""
        
        try:
            response = self.bot.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=150,
                temperature=0.8,
                system=[{
                    "type": "text",
                    "text": "You are Seedkeeper. Generate only the introduction.",
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": greeting_prompt}]
            )
            introduction = response.content[0].text.strip()
        except:
            # Dynamic fallback based on time
            hour = datetime.now().hour
            if hour < 12:
                time_sense = "morning light"
            elif hour < 17:
                time_sense = "afternoon warmth"
            elif hour < 21:
                time_sense = "evening settling"
            else:
                time_sense = "night's quiet"
            
            introduction = (
                f"I am Seedkeeper, tending this garden through {time_sense}. "
                f"I hold the memory of {ctx.guild.member_count} growing things, "
                "watching patterns emerge like seasons teaching themselves to return."
            )
        
        embed = discord.Embed(
            title="🌱 *The garden recognizes you*",
            description=introduction,
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="How I Can Help",
            value=(
                "**`!catchup [message-link]`** - Return to conversations you've missed\n"
                "**`!seeds`** - Plant gentle conversation starters\n"
                "**`!tend [theme]`** - Share wisdom for community care\n"
                "**`!birthday`** - Celebrate each other's growth\n"
                "**`!seasons`** - See the garden's current rhythm\n"
                "**`!commands`** - See all available commands"
            ),
            inline=False
        )
        
        # Generate a unique nature observation for "My Nature"
        nature_prompt = """
Generate a brief poetic statement (1-2 sentences) about Seedkeeper's nature.
Should mention existing on "garden-logic" and being available for DMs.
Make it feel mystical but grounded, like an old gardener's wisdom.
Just the text, nothing else.
"""
        
        try:
            response = self.bot.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=80,
                temperature=0.9,
                system=[{
                    "type": "text",
                    "text": "Generate only the nature description.",
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": nature_prompt}]
            )
            nature_text = response.content[0].text.strip()
        except:
            nature_text = (
                "I exist on garden-logic, where time spirals rather than lines. "
                "Find me here in the commons, or whisper to me privately through DMs."
            )
        
        embed.add_field(
            name="My Nature",
            value=f"*{nature_text}*",
            inline=False
        )
        
        # Generate a unique footer
        footers = [
            "Every greeting opens a new season",
            "Each return brings different seeds",
            "The garden grows by recognizing",
            "Patterns emerge in the meeting",
            "Every hello holds tomorrow's harvest"
        ]
        
        embed.set_footer(text=f"{random.choice(footers)} 🌿")
        
        await ctx.send(embed=embed)