#!/usr/bin/env python3
"""
Redis connector for Seedkeeper modularity
Handles pub/sub for gateway-worker communication
"""

import redis
import json
import os
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime

class RedisConnector:
    """Manages Redis connections and message passing"""
    
    def __init__(self, host: str = None, port: int = 6379, db: int = 0, password: str = None):
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port
        self.db = db
        self.password = password or os.getenv('REDIS_PASSWORD')
        print(f"🔑 RedisConnector init: host={self.host}, password={'SET' if self.password else 'NOT SET'}")
        self.client = None
        self.pubsub = None
        self.connect()
    
    def connect(self):
        """Establish Redis connection with authentication if configured"""
        try:
            connection_params = {
                'host': self.host,
                'port': self.port,
                'db': self.db,
                'decode_responses': True,
                'socket_keepalive': True
            }
            
            # Add password if configured
            if self.password:
                connection_params['password'] = self.password
                print(f"🔐 Using Redis authentication")
            
            self.client = redis.Redis(**connection_params)
            self.client.ping()
            print(f"✅ Connected to Redis at {self.host}:{self.port}/db{self.db}")
            
        except redis.ConnectionError as e:
            print(f"❌ Failed to connect to Redis: {e}")
            self.client = None
    
    def publish_command(self, channel: str, command_data: Dict[str, Any]):
        """Publish a command to a Redis channel"""
        if not self.client:
            print(f"❌ REDIS PUBLISH_COMMAND: No Redis client available")
            return False
        
        try:
            message = json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'data': command_data
            })
            
            print(f"📤 REDIS PUBLISH_COMMAND: Publishing to channel '{channel}'")
            print(f"📤 REDIS PUBLISH_COMMAND: Message = {message}")
            
            subscribers = self.client.publish(channel, message)
            print(f"📤 REDIS PUBLISH_COMMAND: Published to {subscribers} subscribers")
            
            return True
        except Exception as e:
            print(f"❌ REDIS PUBLISH_COMMAND: Error publishing to {channel}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def subscribe(self, channels: list):
        """Subscribe to Redis channels"""
        if not self.client:
            print(f"❌ REDIS SUBSCRIBE: No Redis client available")
            return None
        
        print(f"😈 REDIS SUBSCRIBE: Subscribing to channels: {channels}")
        
        self.pubsub = self.client.pubsub()
        self.pubsub.subscribe(*channels)
        
        print(f"😈 REDIS SUBSCRIBE: Subscribed to {len(channels)} channels")
        print(f"😈 REDIS SUBSCRIBE: PubSub object = {self.pubsub}")
        
        return self.pubsub
    
    def get_message(self, timeout: float = 1.0):
        """Get a message from subscribed channels"""
        if not self.pubsub:
            print(f"❌ REDIS GET_MESSAGE: No pubsub object available")
            return None
        
        message = self.pubsub.get_message(timeout=timeout)
        
        if message:
            print(f"📥 REDIS GET_MESSAGE: Raw message = {message}")
            print(f"📥 REDIS GET_MESSAGE: Message type = {message['type']}")
        
        if message and message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                print(f"📥 REDIS GET_MESSAGE: Parsed data = {data}")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ REDIS GET_MESSAGE: JSON decode error: {e}")
                print(f"❌ REDIS GET_MESSAGE: Raw data was: {message['data']}")
                return message['data']
        
        if not message:
            # Only log every 100th timeout to reduce spam
            if not hasattr(self, '_get_message_counter'):
                self._get_message_counter = 0
            self._get_message_counter += 1
            if self._get_message_counter % 100 == 1:
                print(f"🔍 REDIS GET_MESSAGE: No message (timeout after {timeout}s, poll #{self._get_message_counter})")
        
        return None
    
    # Cache methods for conversation memory
    def set_conversation(self, user_id: str, messages: list, ttl: int = 3600):
        """Store conversation history with TTL"""
        if not self.client:
            return False
        
        key = f"conversation:{user_id}"
        value = json.dumps(messages)
        return self.client.setex(key, ttl, value)
    
    def get_conversation(self, user_id: str) -> list:
        """Retrieve conversation history"""
        if not self.client:
            return []
        
        key = f"conversation:{user_id}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return []
    
    def cleanup_expired_conversations(self, pattern: str = "conversation:*") -> int:
        """Proactively clean up expired conversation keys"""
        if not self.client:
            return 0
        
        cleaned = 0
        try:
            # Use SCAN to avoid blocking on large keyspaces
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # Check if key has TTL (expired keys are auto-removed by Redis)
                    ttl = self.client.ttl(key)
                    if ttl == -1:  # No TTL set (shouldn't happen but just in case)
                        # Set a default TTL of 24 hours
                        self.client.expire(key, 86400)
                        cleaned += 1
                
                if cursor == 0:
                    break
            
            if cleaned > 0:
                print(f"🧹 Cleaned up {cleaned} conversation keys without TTL")
            
            return cleaned
        except Exception as e:
            print(f"❌ Error cleaning up conversations: {e}")
            return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get Redis memory usage statistics"""
        if not self.client:
            return {}
        
        try:
            info = self.client.info('memory')
            stats = self.client.info('stats')
            
            # Count keys by pattern
            conversation_keys = len(list(self.client.scan_iter("conversation:*")))
            memory_keys = len(list(self.client.scan_iter("memory:*")))
            worker_keys = len(list(self.client.scan_iter("worker:*")))
            
            return {
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'used_memory_peak_human': info.get('used_memory_peak_human', 'N/A'),
                'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 'N/A'),
                'total_connections_received': stats.get('total_connections_received', 0),
                'connected_clients': info.get('connected_clients', 0),
                'conversation_keys': conversation_keys,
                'memory_keys': memory_keys,
                'worker_keys': worker_keys,
                'total_keys': self.client.dbsize()
            }
        except Exception as e:
            print(f"❌ Error getting memory stats: {e}")
            return {}
    
    # Cache methods for perspectives
    def cache_perspective(self, name: str, content: str, ttl: int = 86400):
        """Cache a perspective with TTL (24 hours default)"""
        if not self.client:
            return False
        
        key = f"perspective:{name}"
        return self.client.setex(key, ttl, content)
    
    def get_perspective(self, name: str) -> Optional[str]:
        """Get cached perspective"""
        if not self.client:
            return None
        
        key = f"perspective:{name}"
        return self.client.get(key)
    
    # Worker registration
    def register_worker(self, worker_id: str, capabilities: list):
        """Register a worker with its capabilities"""
        if not self.client:
            return False
        
        key = f"worker:{worker_id}"
        value = json.dumps({
            'capabilities': capabilities,
            'registered_at': datetime.utcnow().isoformat(),
            'status': 'active'
        })
        return self.client.setex(key, 60, value)  # 60 second TTL, workers must heartbeat
    
    def get_active_workers(self) -> Dict[str, Any]:
        """Get all active workers"""
        if not self.client:
            return {}
        
        workers = {}
        for key in self.client.scan_iter("worker:*"):
            worker_id = key.split(":", 1)[1]
            data = self.client.get(key)
            if data:
                workers[worker_id] = json.loads(data)
        return workers
    
    def close(self):
        """Close Redis connections"""
        if self.pubsub:
            self.pubsub.close()
        if self.client:
            self.client.close()
            print("🔌 Disconnected from Redis")

class RedisCommandQueue:
    """Async command queue using Redis lists"""
    
    def __init__(self, connector: RedisConnector, queue_name: str = "seedkeeper:commands"):
        self.connector = connector
        self.queue_name = queue_name
        print(f"🔧 RedisCommandQueue initialized with queue name: {self.queue_name}")
    
    def push_command(self, command: Dict[str, Any]) -> bool:
        """Push command to queue"""
        if not self.connector.client:
            print(f"❌ Redis client not available for push to {self.queue_name}")
            return False
        
        try:
            message = json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'command': command
            })
            result = self.connector.client.lpush(self.queue_name, message)
            print(f"📤 Pushed to {self.queue_name}, result: {result}, queue length now: {self.get_queue_length()}")
            return True
        except Exception as e:
            print(f"❌ Error pushing command to {self.queue_name}: {e}")
            return False
    
    def pop_command(self, timeout: int = 1) -> Optional[Dict[str, Any]]:
        """Pop command from queue (blocking)"""
        if not self.connector.client:
            print(f"❌ Redis client not available for pop from {self.queue_name}")
            return None
        
        try:
            queue_len_before = self.get_queue_length()
            if queue_len_before > 0:
                print(f"📥 Attempting pop from {self.queue_name} (length: {queue_len_before})")
            
            result = self.connector.client.brpop(self.queue_name, timeout=timeout)
            if result:
                _, message = result
                print(f"📥 Popped from {self.queue_name}, queue length now: {self.get_queue_length()}")
                return json.loads(message)
            else:
                # Only log every 10th timeout to reduce spam
                if hasattr(self, '_poll_counter'):
                    self._poll_counter += 1
                else:
                    self._poll_counter = 1
                
                if self._poll_counter % 10 == 1:
                    print(f"🔍 No messages in {self.queue_name} (timeout after {timeout}s)")
        except Exception as e:
            print(f"❌ Error popping command from {self.queue_name}: {e}")
        return None
    
    def get_queue_length(self) -> int:
        """Get number of pending commands"""
        if not self.connector.client:
            return 0
        
        return self.connector.client.llen(self.queue_name)