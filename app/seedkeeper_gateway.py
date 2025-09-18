#!/usr/bin/env python3
"""
Seedkeeper Gateway - Persistent Discord connection
Forwards commands to workers via Redis
"""

import discord
from discord.ext import commands
import asyncio
import os
import json
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from redis_connector import RedisConnector, RedisCommandQueue

load_dotenv()

# Get configuration from environment
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')  # Default to 'redis' service name in Docker
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')  # Get Redis password if configured

# Validate required environment variables
if not DISCORD_TOKEN:
    print("❌ DISCORD_BOT_TOKEN not set in environment")
    exit(1)

class SeedkeeperGateway(commands.Bot):
    """Lightweight gateway that maintains Discord connection"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.reactions = True
        intents.members = True  # Required to fetch guild members
        intents.guilds = True   # Required for guild operations
        super().__init__(command_prefix='!', intents=intents)
        
        # Redis connection with authentication
        self.redis = RedisConnector(host=REDIS_HOST, password=REDIS_PASSWORD)
        self.command_queue = RedisCommandQueue(self.redis)
        self.response_subscriber = None
        
        # Start response listener
        self.response_task = None
    
    async def setup_hook(self):
        """Setup async tasks"""
        print(f"😈 GATEWAY SETUP_HOOK: Setting up response subscription")
        
        # Subscribe to response channel
        self.response_subscriber = self.redis.subscribe(['seedkeeper:responses'])
        print(f"😈 GATEWAY SETUP_HOOK: Response subscriber = {self.response_subscriber}")
        
        # Start listening for responses
        self.response_task = asyncio.create_task(self.listen_for_responses())
        print(f"😈 GATEWAY SETUP_HOOK: Started response listener task = {self.response_task}")
    
    async def on_ready(self):
        print(f'🌱 Gateway Online: {self.user}')
        print(f'📡 Connected to {len(self.guilds)} guilds')
        print(f'🔍 User ID: {self.user.id}')
        print(f'🎯 Intents: {self.intents}')
        
        # List guilds
        for guild in self.guilds:
            print(f'  └─ Guild: {guild.name} (ID: {guild.id})')
        
        print(f'🔄 Forwarding commands to Redis workers...')
        print(f'🔧 Debug: Bot ready to receive messages...')
        
        # Only setup subscription if not already done (avoid duplicates)
        if not self.response_subscriber:
            print(f"😈 GATEWAY ON_READY: Setting up response subscription")
            
            # Subscribe to response channel
            self.response_subscriber = self.redis.subscribe(['seedkeeper:responses'])
            print(f"😈 GATEWAY ON_READY: Response subscriber = {self.response_subscriber}")
            
            # Start listening for responses if not already started
            if not self.response_task or self.response_task.done():
                self.response_task = asyncio.create_task(self.listen_for_responses())
                print(f"😈 GATEWAY ON_READY: Started response listener task = {self.response_task}")
        else:
            print(f"😈 GATEWAY ON_READY: Response subscription already active, skipping duplicate")
        
        # Test Redis pubsub is working
        try:
            test_data = {'test': 'gateway_ready', 'timestamp': datetime.utcnow().isoformat()}
            result = self.redis.publish_command('seedkeeper:responses', test_data)
            print(f'🧪 GATEWAY TEST: Published test message, result = {result}')
        except Exception as e:
            print(f'❌ GATEWAY TEST: Failed to publish test message: {e}')
        
        # Register gateway
        self.redis.client.set('gateway:status', json.dumps({
            'online': True,
            'user_id': str(self.user.id),
            'username': str(self.user),
            'guilds': len(self.guilds),
            'started_at': datetime.utcnow().isoformat()
        }))
    
    async def on_message(self, message):
        """Forward all messages to workers"""
        # Don't process bot's own messages
        if message.author == self.user:
            return
        
        # Debug logging
        print(f"📥 Message received: {message.content[:50]}... from {message.author}")
        
        # Package message data
        message_data = {
            'type': 'message',
            'message_id': str(message.id),
            'channel_id': str(message.channel.id),
            'channel_topic': getattr(message.channel, 'topic', None),  # Get channel topic if available
            'guild_id': str(message.guild.id) if message.guild else None,
            'author_id': str(message.author.id),
            'author_name': str(message.author),
            'content': message.content,
            'is_dm': isinstance(message.channel, discord.DMChannel),
            'is_mention': self.user.mentioned_in(message),
            'timestamp': message.created_at.isoformat()
        }
        
        # Handle commands
        if message.content.startswith('!'):
            message_data['type'] = 'command'
            # Parse command and args
            parts = message.content[1:].split(maxsplit=1)
            command = parts[0].lower() if parts else ''
            
            # Handle command aliases
            COMMAND_ALIASES = {
                'whoami': 'about',
                'whoareyou': 'about',
                'hi': 'hello',
                'intro': 'hello'
            }
            
            # Replace alias with actual command
            if command in COMMAND_ALIASES:
                command = COMMAND_ALIASES[command]
            
            message_data['command'] = command
            message_data['args'] = parts[1] if len(parts) > 1 else ''
        
        # Push to queue
        print(f"🔄 Pushing to queue: {message_data.get('type', 'message')} - {message_data.get('command', message.content[:30])}")
        success = self.command_queue.push_command(message_data)
        print(f"📤 Queue push result: {success}")
        
        # For DMs, also cache in conversation history
        if message_data['is_dm']:
            conversation = self.redis.get_conversation(message_data['author_id'])
            conversation.append({
                'role': 'user',
                'content': message.content[:500],
                'timestamp': message_data['timestamp']
            })
            # Keep last 10 messages
            if len(conversation) > 10:
                conversation = conversation[-10:]
            self.redis.set_conversation(message_data['author_id'], conversation)
    
    async def on_raw_reaction_add(self, payload):
        """Forward reactions to workers"""
        if payload.user_id == self.user.id:
            return
        
        reaction_data = {
            'type': 'reaction_add',
            'message_id': str(payload.message_id),
            'channel_id': str(payload.channel_id),
            'guild_id': str(payload.guild_id) if payload.guild_id else None,
            'user_id': str(payload.user_id),
            'emoji': str(payload.emoji),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.command_queue.push_command(reaction_data)
    
    async def listen_for_responses(self):
        """Listen for responses from workers and send to Discord"""
        print(f"😈 GATEWAY LISTEN_FOR_RESPONSES: Started listening for responses")
        
        while True:
            try:
                # Check for responses
                message = self.redis.get_message(timeout=0.1)
                
                if message:
                    print(f"📥 GATEWAY LISTEN_FOR_RESPONSES: Received message = {message}")
                    await self.handle_worker_response(message)
                else:
                    # Only log every 50th poll to reduce spam
                    if not hasattr(self, '_listen_counter'):
                        self._listen_counter = 0
                    self._listen_counter += 1
                    if self._listen_counter % 50 == 1:
                        print(f"🔍 GATEWAY LISTEN_FOR_RESPONSES: No message received (poll #{self._listen_counter})")
                
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"❌ GATEWAY LISTEN_FOR_RESPONSES: Error in response listener: {e}")
                await asyncio.sleep(1)
    
    async def handle_worker_response(self, response_data):
        """Send worker response to Discord"""
        print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Received response_data = {response_data}")
        
        try:
            data = response_data.get('data', {})
            response_type = data.get('type')
            
            print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Extracted data = {data}")
            print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Response type = {response_type}")
            
            if response_type == 'fetch_members':
                # Fetch guild members for birthday matching
                guild_id = data.get('guild_id')
                request_id = data.get('request_id')
                
                if guild_id:
                    try:
                        guild = self.get_guild(int(guild_id))
                        if guild:
                            members = []
                            print(f"🔍 Fetching members from guild: {guild.name} (ID: {guild_id})")
                            for member in guild.members:
                                # Skip bots
                                if member.bot:
                                    continue
                                members.append({
                                    'id': str(member.id),
                                    'name': member.name,
                                    'nick': member.nick if member.nick else '',
                                    'display_name': member.display_name
                                })
                            
                            # Store in Redis for worker to use
                            self.redis.client.setex(
                                f"guild_members:{guild_id}",
                                60,  # 1 minute expiry
                                json.dumps(members)
                            )
                            print(f"✅ Stored {len(members)} guild members for matching (excluding bots)")
                            # Debug: show first few members
                            if members:
                                print(f"📋 Sample members: {', '.join([m['display_name'] for m in members[:5]])}")
                            
                            # Send response back to worker
                            if request_id:
                                response = {
                                    'type': 'members_response',
                                    'request_id': request_id,
                                    'guild_id': guild_id,
                                    'members': members
                                }
                                self.redis.publish_command('seedkeeper:commands', response)
                                print(f"📤 Sent members_response for request {request_id}")
                        else:
                            print(f"❌ Guild {guild_id} not found")
                    except Exception as e:
                        print(f"❌ Error fetching guild members: {e}")
                
            elif response_type == 'message':
                # Send a message
                channel_id_str = data['channel_id']
                is_dm = data.get('is_dm', False)
                
                print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Sending message to channel {channel_id_str} (is_dm: {is_dm})")
                
                channel = None
                if is_dm:
                    # For DMs, get user and create DM channel
                    author_id = data.get('author_id')
                    if author_id:
                        try:
                            user_id = int(author_id)
                            # Try to get user from cache first
                            user = self.get_user(user_id)
                            if not user:
                                # If not in cache, fetch from Discord
                                print(f"🔍 GATEWAY: User {user_id} not in cache, fetching from Discord...")
                                user = await self.fetch_user(user_id)
                            
                            if user:
                                channel = user.dm_channel or await user.create_dm()
                                print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: DM channel = {channel}")
                            else:
                                print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: User {author_id} not found!")
                        except ValueError as e:
                            print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: Invalid author_id '{author_id}': {e}")
                        except Exception as e:
                            print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: Error fetching user {author_id}: {e}")
                    else:
                        print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: No author_id provided for DM!")
                else:
                    # For guild channels, get channel by ID
                    try:
                        channel_id = int(channel_id_str)
                        channel = self.get_channel(channel_id)
                        print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Guild channel = {channel}")
                    except ValueError as e:
                        print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: Invalid channel_id '{channel_id_str}': {e}")
                
                if channel:
                    content = data.get('content')
                    embed_data = data.get('embed')
                    
                    print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Sending content = {content[:100] if content else None}...")
                    
                    embed = None
                    if embed_data:
                        embed = discord.Embed.from_dict(embed_data)
                    
                    sent_message = await channel.send(content=content, embed=embed)
                    print(f"✅ GATEWAY HANDLE_WORKER_RESPONSE: Successfully sent message, ID = {sent_message.id}")
                    
                    # Cache bot response if DM
                    if is_dm:
                        author_id = data.get('author_id')
                        if author_id and content:
                            conversation = self.redis.get_conversation(author_id)
                            conversation.append({
                                'role': 'assistant',
                                'content': content,
                                'timestamp': datetime.utcnow().isoformat()
                            })
                            if len(conversation) > 10:
                                conversation = conversation[-10:]
                            self.redis.set_conversation(author_id, conversation)
                else:
                    print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: Channel not found! channel_id={channel_id_str}, is_dm={is_dm}")
            
            elif response_type == 'typing':
                # Show typing indicator
                channel_id_str = data['channel_id']
                is_dm = data.get('is_dm', False)
                
                print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Showing typing in channel {channel_id_str} (is_dm: {is_dm})")
                
                channel = None
                if is_dm:
                    # For DMs, get user and create DM channel
                    author_id = data.get('author_id')
                    if author_id:
                        try:
                            user = self.get_user(int(author_id))
                            if user:
                                channel = user.dm_channel or await user.create_dm()
                        except ValueError:
                            pass
                else:
                    # For guild channels, get channel by ID
                    try:
                        channel_id = int(channel_id_str)
                        channel = self.get_channel(channel_id)
                    except ValueError:
                        pass
                
                if channel:
                    async with channel.typing():
                        await asyncio.sleep(data.get('duration', 3))
                    print(f"✅ GATEWAY HANDLE_WORKER_RESPONSE: Typing indicator completed")
            
            elif response_type == 'fetch_messages':
                # Fetch messages for catchup command
                channel_id_str = data.get('channel_id')
                message_id_str = data.get('message_id')
                request_id = data.get('request_id')
                limit = data.get('limit', 100)
                requester_id = data.get('requester_id')
                
                print(f"🔍 GATEWAY: Fetching messages from channel {channel_id_str} starting from {message_id_str}")
                
                try:
                    channel = self.get_channel(int(channel_id_str))
                    if channel:
                        # Check if bot has permission to read messages
                        if hasattr(channel, 'permissions_for'):
                            perms = channel.permissions_for(channel.guild.me if hasattr(channel, 'guild') else self.user)
                            if not perms.read_messages or not perms.read_message_history:
                                print(f"❌ GATEWAY: No permission to read messages in channel {channel_id_str}")
                                # Send empty response
                                self.redis.client.setex(
                                    f"messages_response:{request_id}",
                                    30,
                                    json.dumps(None)
                                )
                                return
                        
                        messages = []
                        # Fetch messages after the specified message
                        async for msg in channel.history(limit=limit, after=discord.Object(id=int(message_id_str))):
                            # Don't include bot messages unless they're responses
                            if msg.author.bot and msg.author.id == self.user.id:
                                continue
                            
                            messages.append({
                                'id': str(msg.id),
                                'author': msg.author.name,
                                'author_id': str(msg.author.id),
                                'content': msg.content,
                                'timestamp': msg.created_at.isoformat(),
                                'attachments': len(msg.attachments),
                                'embeds': len(msg.embeds)
                            })
                        
                        # Reverse to get chronological order
                        messages.reverse()
                        
                        # Store in Redis for worker
                        self.redis.client.setex(
                            f"messages_response:{request_id}",
                            30,  # 30 second expiry
                            json.dumps(messages)
                        )
                        print(f"✅ GATEWAY: Fetched {len(messages)} messages for catchup")
                    else:
                        print(f"❌ GATEWAY: Channel {channel_id_str} not found")
                        self.redis.client.setex(
                            f"messages_response:{request_id}",
                            30,
                            json.dumps(None)
                        )
                except Exception as e:
                    print(f"❌ GATEWAY: Error fetching messages: {e}")
                    self.redis.client.setex(
                        f"messages_response:{request_id}",
                        30,
                        json.dumps(None)
                    )
            
            elif response_type == 'reaction':
                # Add a reaction
                channel_id_str = data['channel_id']
                message_id = int(data['message_id'])
                emoji = data['emoji']
                is_dm = data.get('is_dm', False)
                
                print(f"🎯 GATEWAY HANDLE_WORKER_RESPONSE: Adding reaction {emoji} to message {message_id} in channel {channel_id_str} (is_dm: {is_dm})")
                
                channel = None
                if is_dm:
                    # For DMs, get user and create DM channel
                    author_id = data.get('author_id')
                    if author_id:
                        try:
                            user = self.get_user(int(author_id))
                            if user:
                                channel = user.dm_channel or await user.create_dm()
                        except ValueError:
                            pass
                else:
                    # For guild channels, get channel by ID
                    try:
                        channel_id = int(channel_id_str)
                        channel = self.get_channel(channel_id)
                    except ValueError:
                        pass
                
                if channel:
                    message = await channel.fetch_message(message_id)
                    if message:
                        await message.add_reaction(emoji)
                        print(f"✅ GATEWAY HANDLE_WORKER_RESPONSE: Reaction added successfully")
            else:
                print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: Unknown response type: {response_type}")
            
        except Exception as e:
            print(f"❌ GATEWAY HANDLE_WORKER_RESPONSE: Error handling worker response: {e}")
            import traceback
            traceback.print_exc()
    
    async def close(self):
        """Clean shutdown with proper PubSub cleanup"""
        print("🔌 Gateway shutting down...")
        
        # Cancel response listener
        if self.response_task:
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                pass
        
        # Clean up PubSub subscription
        if self.response_subscriber:
            try:
                self.response_subscriber.close()
                print("✅ Closed Redis PubSub subscription")
            except Exception as e:
                print(f"⚠️ Error closing PubSub: {e}")
        
        # Update gateway status
        if self.redis.client:
            self.redis.client.set('gateway:status', json.dumps({
                'online': False,
                'stopped_at': datetime.utcnow().isoformat()
            }))
        
        # Close Redis
        self.redis.close()
        
        await super().close()
    
    async def on_raw_message_create(self, payload):
        """Raw message event for debugging"""
        print(f"🔍 Raw message event received: {payload}")

async def main():
    """Run the gateway"""
    gateway = SeedkeeperGateway()
    
    try:
        await gateway.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n⚠️ Received interrupt signal")
    finally:
        await gateway.close()

if __name__ == "__main__":
    asyncio.run(main())