#!/usr/bin/env python3
"""
Message Delivery Status Producer with Avro Serialization
Simulates a messaging system sending status updates to Kafka in Avro format
"""

import json
import time
import random
import uuid
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import threading
import argparse
import os

from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField

@dataclass
class Config:
    # Kafka settings
    bootstrap_servers: str = None
    schema_registry_url: str = None
    confluent_cloud_api_key: str = None
    confluent_cloud_api_secret: str = None
    confluent_cloud_schema_registry_url: str = None
    confluent_cloud_schema_registry_api_key: str = None
    confluent_cloud_schema_registry_api_secret: str = None

    topic: str = "message_status"
    
    # Database settings
    db_path: str = "message_tracking.db"
    
    # Population settings
    total_phone_numbers: int = 1000
    max_active_messages: int = 100  # Keep this many messages active at once
    carriers: List[str] = None
    
    # Delivery behavior (percentages)
    delivered_rate: float = 0.85  # 85% get delivered
    delayed_rate: float = 0.10    # 10% are delayed
    never_delivered_rate: float = 0.05  # 5% never delivered
    
    # Timing settings (seconds)
    normal_delivery_time: int = 30     # Normal delivery in 30 seconds
    delayed_delivery_time: int = 180   # Delayed delivery in 3 minutes
    heartbeat_interval: int = 30       # Send "sent" status every 30 seconds
    
    # Batch settings
    messages_per_batch: int = 50
    batch_interval: int = 60  # New batch every minute
    
    def __post_init__(self):
        if self.carriers is None:
            self.carriers = ["verizon", "att", "t-mobile"]
        
        # Validate percentages
        total_rate = self.delivered_rate + self.delayed_rate + self.never_delivered_rate
        if abs(total_rate - 1.0) > 0.01:
            raise ValueError(f"Delivery rates must sum to 1.0, got {total_rate}")


class MessageDatabase:
    """SQLite database for tracking phone numbers and message status"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS phone_numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number INTEGER UNIQUE NOT NULL,
                    carrier TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_messages_sent INTEGER DEFAULT 0,
                    total_messages_delivered INTEGER DEFAULT 0
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    phone_number INTEGER NOT NULL,
                    carrier TEXT NOT NULL,
                    status TEXT NOT NULL,
                    delivery_type TEXT NOT NULL,
                    sent_time INTEGER NOT NULL,
                    delivered_time INTEGER NULL,
                    last_heartbeat INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (phone_number) REFERENCES phone_numbers (phone_number)
                )
            ''')
            
            # Index for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_status ON messages (status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages (phone_number)')
            
            conn.commit()
            # print(f"✅ Database initialized: {self.db_path}")  # Commented out for quiet mode
        finally:
            conn.close()
    
    def get_phone_numbers(self, limit: Optional[int] = None) -> List[Dict]:
        """Get phone numbers from database"""
        conn = sqlite3.connect(self.db_path)
        try:
            query = "SELECT phone_number, carrier FROM phone_numbers ORDER BY created_at"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query)
            return [{"phoneNumber": row[0], "carrier": row[1]} for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def add_phone_number(self, phone_number: int, carrier: str) -> bool:
        """Add a new phone number to database"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO phone_numbers (phone_number, carrier) VALUES (?, ?)",
                (phone_number, carrier)
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()
    
    def add_phone_numbers_batch(self, phone_numbers: List[Dict]) -> int:
        """Add multiple phone numbers in batch"""
        conn = sqlite3.connect(self.db_path)
        try:
            data = [(pn["phoneNumber"], pn["carrier"]) for pn in phone_numbers]
            conn.executemany(
                "INSERT OR IGNORE INTO phone_numbers (phone_number, carrier) VALUES (?, ?)",
                data
            )
            conn.commit()
            return conn.total_changes
        finally:
            conn.close()
    
    def get_active_messages(self) -> Dict[str, Dict]:
        """Get all active (non-delivered) messages"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute('''
                SELECT message_id, phone_number, carrier, status, delivery_type, 
                       sent_time, last_heartbeat
                FROM messages 
                WHERE status != 'delivered'
            ''')
            
            active_messages = {}
            for row in cursor.fetchall():
                message_id, phone_number, carrier, status, delivery_type, sent_time, last_heartbeat = row
                active_messages[message_id] = {
                    "phone_data": {
                        "phoneNumber": phone_number,
                        "carrier": carrier,
                        "messageId": message_id
                    },
                    "sent_time": sent_time,
                    "delivery_type": delivery_type,
                    "last_heartbeat": last_heartbeat
                }
            
            return active_messages
        finally:
            conn.close()
    
    def add_message(self, message_id: str, phone_data: Dict, delivery_type: str, sent_time: int):
        """Add a new message to database"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''
                INSERT INTO messages 
                (message_id, phone_number, carrier, status, delivery_type, sent_time, last_heartbeat)
                VALUES (?, ?, ?, 'sent', ?, ?, ?)
            ''', (message_id, phone_data["phoneNumber"], phone_data["carrier"], 
                  delivery_type, sent_time, sent_time))
            
            # Update phone number stats
            conn.execute('''
                UPDATE phone_numbers 
                SET total_messages_sent = total_messages_sent + 1 
                WHERE phone_number = ?
            ''', (phone_data["phoneNumber"],))
            
            conn.commit()
        finally:
            conn.close()
    
    def update_message_status(self, message_id: str, status: str, timestamp: int = None):
        """Update message status"""
        conn = sqlite3.connect(self.db_path)
        try:
            if status == 'delivered':
                conn.execute('''
                    UPDATE messages 
                    SET status = ?, delivered_time = ? 
                    WHERE message_id = ?
                ''', (status, timestamp, message_id))
                
                # Update phone number delivery stats
                conn.execute('''
                    UPDATE phone_numbers 
                    SET total_messages_delivered = total_messages_delivered + 1 
                    WHERE phone_number = (SELECT phone_number FROM messages WHERE message_id = ?)
                ''', (message_id,))
            else:
                conn.execute('''
                    UPDATE messages 
                    SET last_heartbeat = ? 
                    WHERE message_id = ?
                ''', (timestamp, message_id))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_delivered_messages(self) -> set:
        """Get set of delivered message IDs"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT message_id FROM messages WHERE status = 'delivered'")
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()
    
    def get_never_deliver_messages(self) -> set:
        """Get set of never-deliver message IDs"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT message_id FROM messages WHERE delivery_type = 'never'")
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Phone number stats
            cursor = conn.execute("SELECT COUNT(*) FROM phone_numbers")
            total_phones = cursor.fetchone()[0]
            
            # Message stats
            cursor = conn.execute("SELECT status, COUNT(*) FROM messages GROUP BY status")
            message_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Carrier breakdown
            cursor = conn.execute('''
                SELECT p.carrier, COUNT(*) as active_messages
                FROM phone_numbers p
                JOIN messages m ON p.phone_number = m.phone_number
                WHERE m.status != 'delivered'
                GROUP BY p.carrier
            ''')
            carrier_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_phones": total_phones,
                "message_stats": message_stats,
                "carrier_stats": carrier_stats
            }
        finally:
            conn.close()

class MessageProducer:
    def __init__(self, config: Config):
        self.config = config
        
        # Setup logging (quiet mode)
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Track errors
        self.error_count = 0
        self.last_error = None
        
        # Initialize database
        self.db = MessageDatabase(config.db_path)
        
        # Avro schemas
        self.key_schema = """
        {
            "type": "record",
            "name": "MessageKey",
            "fields": [
                {"name": "messageId", "type": "string"}
            ]
        }
        """
        
        self.value_schema = """
        {
            "type": "record",
            "name": "MessageStatus",
            "fields": [
                {"name": "status", "type": "string"},
                {"name": "phoneNumber", "type": "long"},
                {"name": "carrier", "type": "string"},
                {"name": "timestamp", "type": "long"}
            ]
        }
        """
        
        # Setup Schema Registry and serializers
        try:
            self.schema_registry = SchemaRegistryClient({
                'url': config.schema_registry_url,
                'basic.auth.user.info': f"{config.confluent_cloud_schema_registry_api_key}:{config.confluent_cloud_schema_registry_api_secret}"
            })
            
            self.key_serializer = AvroSerializer(
                self.schema_registry,
                self.key_schema
            )
            
            self.value_serializer = AvroSerializer(
                self.schema_registry,
                self.value_schema
            )
        except Exception as e:
            self.logger.error(f"Failed to setup Schema Registry: {e}")
            raise
        
        # Setup Kafka producer
        try:
            producer_config = {
                'bootstrap.servers': config.bootstrap_servers,
                'client.id': 'message-status-producer',
                'security.protocol': 'SASL_SSL',
                'sasl.mechanism': 'PLAIN',
                'sasl.username': config.confluent_cloud_api_key,
                'sasl.password': config.confluent_cloud_api_secret,
                'acks': 'all',
                'retries': 3,
                'retry.backoff.ms': 1000,
                'request.timeout.ms': 30000,
                'delivery.timeout.ms': 60000
            }
            
            self.producer = Producer(producer_config)
        except Exception as e:
            self.logger.error(f"Failed to setup Kafka producer: {e}")
            raise
        
        # Initialize phone number population and load existing state
        self._ensure_phone_numbers()
        
        # Load existing message states from database
        self.active_messages = self.db.get_active_messages()
        self.delivered_messages = self.db.get_delivered_messages()
        self.never_deliver_messages = self.db.get_never_deliver_messages()
        
        # Silent startup
        
        # Threading control
        self.running = False
        self.threads: List[threading.Thread] = []
    
    def _ensure_phone_numbers(self):
        """Ensure we have enough phone numbers in the database"""
        existing_phones = self.db.get_phone_numbers()
        
        if len(existing_phones) < self.config.total_phone_numbers:
            needed = self.config.total_phone_numbers - len(existing_phones)
            new_phones = self._generate_phone_numbers(needed)
            added = self.db.add_phone_numbers_batch(new_phones)
    
    def _generate_phone_numbers(self, count: int) -> List[Dict]:
        """Generate population of phone numbers with carriers"""
        phones = []
        for i in range(count):
            # Generate realistic-looking phone numbers
            area_code = random.choice([212, 415, 713, 404, 602, 503])
            exchange = random.randint(200, 999)
            number = random.randint(1000, 9999)
            phone = int(f"{area_code}{exchange}{number}")
            
            carrier = random.choice(self.config.carriers)
            phones.append({
                "phoneNumber": phone,
                "carrier": carrier
            })
        return phones
    
    def _get_current_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(datetime.now().timestamp() * 1000)
    
    def _send_status(self, phone_data: Dict, status: str, timestamp: int = None):
        """Send a status message to Kafka in Avro format"""
        if timestamp is None:
            timestamp = self._get_current_timestamp()
        
        # Prepare key and value as dictionaries
        key_data = {"messageId": phone_data["messageId"]}
        
        value_data = {
            "status": status,
            "phoneNumber": phone_data["phoneNumber"],
            "carrier": phone_data["carrier"],
            "timestamp": timestamp
        }
        
        try:
            # Serialize to Avro
            self.logger.debug(f"Serializing message for {phone_data['messageId'][:8]}...")
            serialization_context = SerializationContext(self.config.topic, MessageField.KEY)
            serialized_key = self.key_serializer(key_data, serialization_context)
            
            serialization_context = SerializationContext(self.config.topic, MessageField.VALUE)
            serialized_value = self.value_serializer(value_data, serialization_context)
            
            # Send to Kafka
            self.logger.debug(f"Producing message to topic {self.config.topic}")
            self.producer.produce(
                topic=self.config.topic,
                key=serialized_key,
                value=serialized_value,
                callback=lambda err, msg, phone_data=phone_data, status=status: self._delivery_report(err, msg, phone_data, status)
            )
            
            # Poll for delivery reports
            self.producer.poll(0)
            
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            self.logger.error(f"Failed to send message for {phone_data['messageId'][:8]}...: {e}")
            print(f"ERROR: Failed to send {status} for {phone_data['messageId'][:8]}... ({phone_data['carrier']}): {e}")
            raise
    
    def _delivery_report(self, err, msg, phone_data, status):
        """Kafka delivery callback with error reporting"""
        if err is not None:
            self.error_count += 1
            self.last_error = str(err)
            error_msg = f"❌ DELIVERY FAILED: {status} for {phone_data['messageId'][:8]}... - {err}"
            self.logger.error(error_msg)
            print(error_msg)
        # Success messages are now silent to reduce noise
    
    def _classify_message(self, phone_data: Dict) -> str:
        """Determine delivery behavior for a message"""
        rand = random.random()
        
        if rand < self.config.delivered_rate:
            return "normal"
        elif rand < self.config.delivered_rate + self.config.delayed_rate:
            return "delayed"
        else:
            return "never"
    
    def _send_batch(self):
        """Send a batch of new messages"""
        # Check if we need more phone numbers to maintain constant stream
        if len(self.active_messages) < self.config.max_active_messages:
            needed_messages = min(
                self.config.messages_per_batch,
                self.config.max_active_messages - len(self.active_messages)
            )
            
            # Get available phone numbers (excluding those with active messages)
            all_phones = self.db.get_phone_numbers()
            active_phone_numbers = {msg_data["phone_data"]["phoneNumber"] for msg_data in self.active_messages.values()}
            available_phones = [p for p in all_phones if p["phoneNumber"] not in active_phone_numbers]
            
                         # If we don't have enough available phones, generate more
            if len(available_phones) < needed_messages:
                new_phones_needed = needed_messages - len(available_phones)
                new_phones = self._generate_phone_numbers(new_phones_needed)
                self.db.add_phone_numbers_batch(new_phones)
                available_phones.extend(new_phones)
            
            # Select phones for this batch
            batch_size = min(needed_messages, len(available_phones))
            batch_phones = random.sample(available_phones, batch_size)
            
            current_time = self._get_current_timestamp()
            
            for phone_data in batch_phones:
                # Create new message ID for this phone number
                message_id = str(uuid.uuid4())
                phone_data["messageId"] = message_id
                
                # Classify delivery behavior
                delivery_type = self._classify_message(phone_data)
                
                # Save to database first
                self.db.add_message(message_id, phone_data, delivery_type, current_time)
                
                # Send initial "sent" status
                self._send_status(phone_data, "sent", current_time)
                
                # Track message state in memory
                self.active_messages[message_id] = {
                    "phone_data": phone_data,
                    "sent_time": current_time,
                    "delivery_type": delivery_type,
                    "last_heartbeat": current_time
                }
                
                # Mark messages that will never be delivered
                if delivery_type == "never":
                    self.never_deliver_messages.add(message_id)
        else:
            batch_phones = []
        
        # Flush and wait for delivery reports
        try:
            remaining = self.producer.flush(timeout=10)
            if remaining > 0:
                print(f"⚠️  WARNING: {remaining} messages still in queue after flush timeout")
        except Exception as e:
            print(f"❌ ERROR during flush: {e}")
        
        if len(batch_phones) > 0:
            print(f"📤 Sent {len(batch_phones)} messages", flush=True)
    
    def _send_heartbeats(self):
        """Send periodic 'sent' status for undelivered messages"""
        current_time = self._get_current_timestamp()
        heartbeat_count = 0
        
        for message_id, msg_data in list(self.active_messages.items()):
            # Skip if already delivered
            if message_id in self.delivered_messages:
                continue
            
            # Send heartbeat if enough time has passed
            if current_time - msg_data["last_heartbeat"] >= (self.config.heartbeat_interval * 1000):
                self._send_status(msg_data["phone_data"], "sent", current_time)
                msg_data["last_heartbeat"] = current_time
                
                # Update database with new heartbeat time
                self.db.update_message_status(message_id, "sent", current_time)
                
                heartbeat_count += 1
        
        if heartbeat_count > 0:
            try:
                remaining = self.producer.flush(timeout=5)
                if remaining > 0:
                    print(f"⚠️  WARNING: {remaining} heartbeat messages still in queue")
            except Exception as e:
                print(f"❌ ERROR flushing heartbeat messages: {e}")
            
            print(f"💓 {heartbeat_count} heartbeats", flush=True)
    
    def _process_deliveries(self):
        """Process scheduled deliveries"""
        current_time = self._get_current_timestamp()
        delivered_count = 0
        
        for message_id, msg_data in list(self.active_messages.items()):
            # Skip if already delivered or never will be
            if message_id in self.delivered_messages or message_id in self.never_deliver_messages:
                continue
            
            delivery_type = msg_data["delivery_type"]
            sent_time = msg_data["sent_time"]
            time_elapsed = current_time - sent_time
            
            should_deliver = False
            
            if delivery_type == "normal" and time_elapsed >= (self.config.normal_delivery_time * 1000):
                should_deliver = True
            elif delivery_type == "delayed" and time_elapsed >= (self.config.delayed_delivery_time * 1000):
                should_deliver = True
            
            if should_deliver:
                self._send_status(msg_data["phone_data"], "delivered", current_time)
                
                # Update database with delivery status
                self.db.update_message_status(message_id, "delivered", current_time)
                
                self.delivered_messages.add(message_id)
                delivered_count += 1
        
        if delivered_count > 0:
            try:
                remaining = self.producer.flush(timeout=5)
                if remaining > 0:
                    print(f"⚠️  WARNING: {remaining} delivery messages still in queue")
            except Exception as e:
                print(f"❌ ERROR flushing delivery messages: {e}")
            
            print(f"✅ {delivered_count} delivered", flush=True)
    
    def _cleanup_delivered_messages(self):
        """Remove delivered messages from active tracking"""
        for message_id in list(self.active_messages.keys()):
            if message_id in self.delivered_messages:
                del self.active_messages[message_id]
    
    def _batch_thread(self):
        """Thread for sending new message batches"""
        while self.running:
            self._send_batch()
            time.sleep(self.config.batch_interval)
    
    def _heartbeat_thread(self):
        """Thread for sending heartbeat messages"""
        while self.running:
            time.sleep(self.config.heartbeat_interval)
            if self.running:  # Check again after sleep
                self._send_heartbeats()
    
    def _delivery_thread(self):
        """Thread for processing deliveries"""
        while self.running:
            time.sleep(5)  # Check every 5 seconds
            if self.running:
                self._process_deliveries()
                self._cleanup_delivered_messages()
    
    def start(self):
        """Start the message producer"""
        print("🚀 Producer starting...", flush=True)
        
        self.running = True
        
        # Start threads
        self.threads = [
            threading.Thread(target=self._batch_thread, name="BatchThread"),
            threading.Thread(target=self._heartbeat_thread, name="HeartbeatThread"),
            threading.Thread(target=self._delivery_thread, name="DeliveryThread")
        ]
        
        for thread in self.threads:
            thread.start()
        
        print("✅ Running (Ctrl+C to stop)", flush=True)
    
    def stop(self):
        """Stop the message producer"""
        print("\nStopping...")
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        # Final flush
        try:
            remaining = self.producer.flush(timeout=10)
            if remaining > 0:
                print(f"⚠️  WARNING: {remaining} messages still in queue after final flush")
        except Exception as e:
            print(f"❌ ERROR during final flush: {e}")
        
        print("🛑 Stopped.")
    
    def status(self):
        """Print current status"""
        db_stats = self.db.get_stats()
        
        print(f"\n--- Producer Status ---", flush=True)
        print(f"📱 Total phone numbers: {db_stats['total_phones']}", flush=True)
        print(f"📨 Active messages: {len(self.active_messages)}", flush=True)
        print(f"✅ Delivered messages: {len(self.delivered_messages)}", flush=True)
        print(f"❌ Never-deliver messages: {len(self.never_deliver_messages)}", flush=True)
        print(f"🚨 Error count: {self.error_count}", flush=True)
        if self.last_error:
            print(f"Last error: {self.last_error}", flush=True)
        
        # Database message stats
        if db_stats['message_stats']:
            print(f"\n📊 Database Message Stats:", flush=True)
            for status, count in db_stats['message_stats'].items():
                print(f"  {status}: {count}", flush=True)
        
        # Active messages by carrier
        if db_stats['carrier_stats']:
            print(f"\n📡 Active by carrier:", flush=True)
            for carrier, count in db_stats['carrier_stats'].items():
                print(f"  {carrier}: {count}", flush=True)


class DryRunProducer:
    """Dry-run version that echoes messages to console instead of sending to Kafka"""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Generate phone number population (in-memory for dry-run)
        self.phone_numbers = self._generate_phone_numbers(config.total_phone_numbers)
        
        # Track message states (in-memory for dry-run)
        self.active_messages: Dict[str, Dict] = {}
        self.delivered_messages: set = set()
        self.never_deliver_messages: set = set()
        
        # Threading control
        self.running = False
        self.threads: List[threading.Thread] = []
    
    def _generate_phone_numbers(self, count: int) -> List[Dict]:
        """Generate population of phone numbers with carriers"""
        phones = []
        for i in range(count):
            # Generate realistic-looking phone numbers
            area_code = random.choice([212, 415, 713, 404, 602, 503])
            exchange = random.randint(200, 999)
            number = random.randint(1000, 9999)
            phone = int(f"{area_code}{exchange}{number}")
            
            carrier = random.choice(self.config.carriers)
            phones.append({
                "phoneNumber": phone,
                "carrier": carrier,
                "messageId": str(uuid.uuid4())  # Consistent message ID per phone
            })
        return phones
    
    def _get_current_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(datetime.now().timestamp() * 1000)
    
    def _send_status(self, phone_data: Dict, status: str, timestamp: int = None):
        """Echo status message to console instead of sending to Kafka"""
        if timestamp is None:
            timestamp = self._get_current_timestamp()
        
        # Create the message data
        key_data = {"messageId": phone_data["messageId"]}
        value_data = {
            "status": status,
            "phoneNumber": phone_data["phoneNumber"],
            "carrier": phone_data["carrier"],
            "timestamp": timestamp
        }
        
        # Echo to console instead of sending to Kafka (compact format)
        readable_time = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S')
        print(f"[{readable_time}] {status.upper()}: {phone_data['phoneNumber']} ({phone_data['carrier']})", flush=True)
    
    def _classify_message(self, phone_data: Dict) -> str:
        """Determine delivery behavior for a message"""
        rand = random.random()
        
        if rand < self.config.delivered_rate:
            return "normal"
        elif rand < self.config.delivered_rate + self.config.delayed_rate:
            return "delayed"
        else:
            return "never"
    
    def _send_batch(self):
        """Send a batch of new messages"""
        batch = random.sample(self.phone_numbers, self.config.messages_per_batch)
        current_time = self._get_current_timestamp()
        
        # Batch sent (silent in dry-run)
        
        for phone_data in batch:
            # Don't send if already active
            if phone_data["messageId"] in self.active_messages:
                continue
            
            # Classify delivery behavior
            delivery_type = self._classify_message(phone_data)
            
            # Send initial "sent" status
            self._send_status(phone_data, "sent", current_time)
            
            # Track message state
            self.active_messages[phone_data["messageId"]] = {
                "phone_data": phone_data,
                "sent_time": current_time,
                "delivery_type": delivery_type,
                "last_heartbeat": current_time
            }
            
            # Mark messages that will never be delivered
            if delivery_type == "never":
                self.never_deliver_messages.add(phone_data["messageId"])
        
        # Batch complete (silent)
    
    def _send_heartbeats(self):
        """Send periodic 'sent' status for undelivered messages"""
        current_time = self._get_current_timestamp()
        heartbeat_count = 0
        
        messages_for_heartbeat = []
        for message_id, msg_data in list(self.active_messages.items()):
            # Skip if already delivered
            if message_id in self.delivered_messages:
                continue
            
            # Send heartbeat if enough time has passed
            if current_time - msg_data["last_heartbeat"] >= (self.config.heartbeat_interval * 1000):
                messages_for_heartbeat.append(msg_data)
                msg_data["last_heartbeat"] = current_time
                heartbeat_count += 1
        
        if heartbeat_count > 0:
            for msg_data in messages_for_heartbeat:
                self._send_status(msg_data["phone_data"], "sent", current_time)
    
    def _process_deliveries(self):
        """Process scheduled deliveries"""
        current_time = self._get_current_timestamp()
        messages_to_deliver = []
        
        for message_id, msg_data in list(self.active_messages.items()):
            # Skip if already delivered or never will be
            if message_id in self.delivered_messages or message_id in self.never_deliver_messages:
                continue
            
            delivery_type = msg_data["delivery_type"]
            sent_time = msg_data["sent_time"]
            time_elapsed = current_time - sent_time
            
            should_deliver = False
            
            if delivery_type == "normal" and time_elapsed >= (self.config.normal_delivery_time * 1000):
                should_deliver = True
            elif delivery_type == "delayed" and time_elapsed >= (self.config.delayed_delivery_time * 1000):
                should_deliver = True
            
            if should_deliver:
                messages_to_deliver.append(msg_data)
                self.delivered_messages.add(message_id)
        
        if messages_to_deliver:
            for msg_data in messages_to_deliver:
                self._send_status(msg_data["phone_data"], "delivered", current_time)
    
    def _cleanup_delivered_messages(self):
        """Remove delivered messages from active tracking"""
        for message_id in list(self.active_messages.keys()):
            if message_id in self.delivered_messages:
                del self.active_messages[message_id]
    
    def _batch_thread(self):
        """Thread for sending new message batches"""
        while self.running:
            self._send_batch()
            time.sleep(self.config.batch_interval)
    
    def _heartbeat_thread(self):
        """Thread for sending heartbeat messages"""
        while self.running:
            time.sleep(self.config.heartbeat_interval)
            if self.running:  # Check again after sleep
                self._send_heartbeats()
    
    def _delivery_thread(self):
        """Thread for processing deliveries"""
        while self.running:
            time.sleep(5)  # Check every 5 seconds
            if self.running:
                self._process_deliveries()
                self._cleanup_delivered_messages()
    
    def start(self):
        """Start the dry-run producer"""
        print("🧪 DRY-RUN starting...", flush=True)
        
        self.running = True
        
        # Start threads
        self.threads = [
            threading.Thread(target=self._batch_thread, name="DryRunBatchThread"),
            threading.Thread(target=self._heartbeat_thread, name="DryRunHeartbeatThread"),
            threading.Thread(target=self._delivery_thread, name="DryRunDeliveryThread")
        ]
        
        for thread in self.threads:
            thread.start()
        
        print("✅ DRY-RUN running (Ctrl+C to stop)", flush=True)
    
    def stop(self):
        """Stop the dry-run producer"""
        print("\nStopping DRY-RUN...")
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        print("DRY-RUN stopped.")
    
    def status(self):
        """Print current status"""
        print(f"\n--- DRY-RUN Producer Status ---", flush=True)
        print(f"Active messages: {len(self.active_messages)}", flush=True)
        print(f"Delivered messages: {len(self.delivered_messages)}", flush=True)
        print(f"Never-deliver messages: {len(self.never_deliver_messages)}", flush=True)
        
        # Breakdown by carrier
        carrier_stats = {}
        for msg_data in self.active_messages.values():
            carrier = msg_data["phone_data"]["carrier"]
            carrier_stats[carrier] = carrier_stats.get(carrier, 0) + 1
        
        print("Active by carrier:", carrier_stats, flush=True)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Message Delivery Status Producer')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Echo messages to stdout instead of sending to Kafka')
    args = parser.parse_args()
    
    # Load environment variables
    env = os.environ
    
    # Example configuration - adjust as needed
    config = Config(
        bootstrap_servers=env.get("BOOTSTRAP_URL"),
        schema_registry_url=env.get("SCHEMA_REGISTRY_URL"),
        confluent_cloud_api_key=env.get("CONFLUENT_API_KEY"),
        confluent_cloud_api_secret=env.get("CONFLUENT_API_SECRET"),
        confluent_cloud_schema_registry_url=env.get("SCHEMA_REGISTRY_URL"),
        confluent_cloud_schema_registry_api_key=env.get("SCHEMA_REGISTRY_API_KEY"),
        confluent_cloud_schema_registry_api_secret=env.get("SCHEMA_REGISTRY_API_SECRET"),
        topic="message_status",
        db_path="message_tracking.db",
        total_phone_numbers=500,      # Pool of phone numbers to use
        max_active_messages=50,       # Keep this many messages active at once
        delivered_rate=0.80,          # 80% delivered normally
        delayed_rate=0.15,            # 15% delayed (good for testing Verizon issues)
        never_delivered_rate=0.05,    # 5% never delivered
        normal_delivery_time=45,      # 45 seconds normal
        delayed_delivery_time=150,    # 2.5 minutes delayed
        messages_per_batch=10,        # Send fewer per batch for constant stream
        batch_interval=30             # Send new batch every 30 seconds
    )

    # print(config)  # Disabled for quiet mode
    
    try:
        if args.dry_run:
            producer = DryRunProducer(config)
        else:
            try:
                producer = MessageProducer(config)
            except Exception as e:
                print(f"❌ FATAL: Failed to initialize producer: {e}")
                return
        
        producer.start()
        
        # Keep running and show status periodically
        while True:
            time.sleep(30)  # Show status every 30 seconds
            producer.status()
                
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        producer.stop()
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        logging.exception("Fatal error in main loop")
        if 'producer' in locals():
            producer.stop()

if __name__ == "__main__":
    main()