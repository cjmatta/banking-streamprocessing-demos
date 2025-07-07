## Use Case 1 - Message Delivery Status Producer

**Objective:** Track the delivery status of messages (e.g., SMS OTPs) sent via a third-party provider (Relay) to ensure they are delivered within a specified time frame (e.g., 1-2 minutes).
**Problem:** A previous issue occurred where messages to Verizon phones were delayed, and there was no mechanism to catch the delay proactively.
**Proposed Solution:** Build a stateful stream processor that stores message IDs and their status (e.g., "sent," "delivered") in a stateful stream processor. Using a timestamp from the message, the query should send records out to an alerting topic if messages are undelivered after a configurable timeout.
