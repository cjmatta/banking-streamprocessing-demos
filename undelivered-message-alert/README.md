# Undelivered Message Alert Producer

A message delivery status producer that simulates a real-world messaging system for banking and telecommunications use cases. This producer generates phone numbers and tracks message delivery statuses through various stages (sent, delivered, delayed, failed).

## Features

- **Realistic Message Lifecycle**: Simulates message delivery with configurable success/failure rates
- **Multi-Carrier Support**: Supports major carriers (Verizon, AT&T, T-Mobile)
- **Kafka Integration**: Publishes message status updates to Kafka topics with Avro serialization
- **SQLite Tracking**: Local database for message and phone number tracking
- **Configurable Delivery Behavior**: Customizable delivery rates and timing
- **Dry Run Mode**: Test without sending to Kafka
- **Real-time Statistics**: Monitor delivery rates and system performance

## Message States

- **Sent**: Initial state when message is dispatched
- **Delivered**: Message successfully delivered (85% default)
- **Delayed**: Message delayed but will eventually deliver (10% default)
- **Failed**: Message will never be delivered (5% default)

## Quick Start

### Installation

```bash
# Install dependencies
uv install

# Or with pip
pip install -r requirements.txt
```

### Configuration

The producer can be configured via environment variables or command-line arguments:

```bash
# Kafka Configuration
export BOOTSTRAP_SERVERS="localhost:9092"
export SCHEMA_REGISTRY_URL="http://localhost:8081"

# For Confluent Cloud
export CONFLUENT_CLOUD_API_KEY="your-api-key"
export CONFLUENT_CLOUD_API_SECRET="your-api-secret"
export CONFLUENT_CLOUD_SCHEMA_REGISTRY_URL="https://your-schema-registry.com"
```

### Usage

#### Basic Usage (Dry Run)
```bash
python phone_message_producer.py --dry-run
```

#### Production Mode
```bash
python phone_message_producer.py \
  --bootstrap-servers localhost:9092 \
  --schema-registry-url http://localhost:8081 \
  --topic message_status
```

#### Custom Configuration
```bash
python phone_message_producer.py \
  --total-phone-numbers 500 \
  --max-active-messages 50 \
  --delivered-rate 0.80 \
  --delayed-rate 0.15 \
  --never-delivered-rate 0.05 \
  --batch-interval 30
```

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--total-phone-numbers` | Total phone numbers to generate | 1000 |
| `--max-active-messages` | Maximum concurrent active messages | 100 |
| `--delivered-rate` | Percentage of messages delivered | 0.85 |
| `--delayed-rate` | Percentage of messages delayed | 0.10 |
| `--never-delivered-rate` | Percentage of messages never delivered | 0.05 |
| `--normal-delivery-time` | Normal delivery time (seconds) | 30 |
| `--delayed-delivery-time` | Delayed delivery time (seconds) | 180 |
| `--batch-interval` | Batch sending interval (seconds) | 60 |
| `--messages-per-batch` | Messages per batch | 50 |

## Data Format

### Avro Schema
```json
{
  "messageId": "uuid",
  "phoneNumber": "long",
  "carrier": "string",
  "status": "string",
  "timestamp": "long"
}
```

### Example Message
```json
{
  "messageId": "123e4567-e89b-12d3-a456-426614174000",
  "phoneNumber": 15551234567,
  "carrier": "verizon",
  "status": "sent",
  "timestamp": 1645123456789
}
```

## Database Schema

The producer uses SQLite to track:
- **phone_numbers**: Phone number registry with carrier mapping
- **messages**: Message tracking with delivery status and timing

## Use Cases

- **Banking Notifications**: Simulate SMS alerts for banking transactions
- **Telecommunications Testing**: Test message delivery reliability
- **Stream Processing**: Generate realistic data for Kafka/streaming pipelines
- **Alert System Development**: Test undelivered message detection systems

## Monitoring

The producer provides real-time statistics:
- Active messages count
- Delivery success rates
- Carrier distribution
- Database statistics

## Dependencies

- `confluent-kafka`: Kafka client with Avro support
- `fastavro`: Fast Avro serialization
- `sqlite3`: Local message tracking
- `attrs`: Configuration management

## Architecture

```
Phone Numbers → Message Producer → Kafka Topic → Stream Processing
     ↓                ↓
SQLite Database ← Status Tracking
```

## Example Integration

This producer is designed to work with stream processing systems that detect undelivered messages and trigger alerts. Perfect for:

- Real-time fraud detection systems
- Customer notification reliability monitoring
- Telecommunications infrastructure testing
- Banking compliance and monitoring systems
