# Temperature Monitoring & Blockchain Integration

<p align="center">

<img src="https://img.shields.io/badge/Status-Prototype%20%2F%20Development-orange?style=flat-square"/>

<img src="https://img.shields.io/badge/Platform-Raspberry%20Pi-C51A4A?style=flat-square&logo=raspberry-pi"/>

<img src="https://img.shields.io/badge/Blockchain-EVM%20Compatible-blue?style=flat-square"/>

<img src="https://img.shields.io/badge/Alerts-Telegram-2CA5E0?style=flat-square&logo=telegram"/>

<img src="https://img.shields.io/badge/Language-Python-green?style=flat-square"/>

<img src="https://img.shields.io/badge/Sensor-DHT22-yellow?style=flat-square"/>

<img src="https://img.shields.io/badge/Licence-MIT-success?style=flat-square"/>

</p>

> IoT-based Temperature and Humidity Monitoring System for Raspberry Pi with Blockchain Integration.
>
> The system continuously monitors environmental conditions using DHT22 sensors, detects threshold violations, stores records on-chain and off-chain, sends real-time alerts via Telegram, and records critical events on blockchain for tamper-resistant monitoring and reporting.

---

## Table of Contents

* [Overview](#overview)
* [Problem Statement](#problem-statement)
* [Solution](#solution)
* [System Architecture](#system-architecture)
* [Features](#features)
* [Technology Stack](#technology-stack)
* [Project Structure](#project-structure)
* [Installation](#installation)
* [Configuration](#configuration)
* [Workflow](#workflow)
* [Blockchain Integration](#blockchain-integration)
* [Telegram Notifications](#telegram-notifications)
* [Future Improvements](#future-improvements)
* [Licence](#licence)

---

## Overview

This project implements an intelligent environmental monitoring platform running on a Raspberry Pi device. The system continuously captures temperature and humidity values from connected sensors and performs automated monitoring tasks including:

* Real-time sensor acquisition
* Temperature threshold monitoring
* Long-duration breach detection
* Blockchain event recording
* Telegram alert notifications
* CSV report generation
* SHA-256 file integrity verification
* Automatic recovery detection

The platform is designed for use cases requiring trusted monitoring and tamper-proof records including:

* Cold-chain monitoring
* Pharmaceutical storage
* Food transportation
* Laboratory monitoring
* Smart warehouse environments
* IoT asset monitoring

---

## Problem Statement

Traditional monitoring systems commonly suffer from several issues:

| Problem                | Impact                                 |
| ---------------------- | -------------------------------------- |
| Centralized storage    | Vulnerable to modification or deletion |
| Manual reporting       | Slow incident response                 |
| Delayed notifications  | Potential product loss                 |
| Weak audit trails      | Difficult compliance verification      |
| Lack of data integrity | Records can be altered                 |

Environmental-sensitive industries require systems capable of:

* Continuous monitoring
* Automated incident detection
* Real-time alerts
* Immutable record storage
* Integrity verification

---

## Solution

The proposed solution combines IoT monitoring with blockchain technology.

### Monitoring Flow

```text
DHT22 Sensor

     ↓

Raspberry Pi Monitoring Service

     ↓

Temperature Threshold Validation

     ↓

40-minute Breach Detection

     ↓

┌────────────────┬────────────────┐
│                │                │
▼                ▼                ▼

CSV Storage    Telegram Alert   Blockchain Record

│               │                │

▼               ▼                ▼

SHA256 Hash    Real-time Alert   Immutable Log
```

---

## System Architecture

```text
┌──────────────────────────────────────────────┐
│              Raspberry Pi                    │
│                                               │
│  ┌─────────────────────────────────────┐      │
│  │ Sensor Manager                      │      │
│  │ DHT22 Temperature/Humidity Sensor   │      │
│  └──────────────┬──────────────────────┘      │
│                 │                             │
│                 ▼                             │
│      ┌────────────────────────┐              │
│      │ Breach Tracker         │              │
│      │ Temperature Validation │              │
│      └─────────────┬──────────┘              │
│                    │                         │
│      ┌─────────────┼──────────────┐          │
│      │             │              │          │
│      ▼             ▼              ▼          │
│ CSV Manager   Telegram      Blockchain       │
│ Local Logs    Notification   Manager         │
│                                            │
└──────────────────────────────────────────────┘
```

---

## Features

### Real-Time Sensor Monitoring

* Reads temperature and humidity from DHT22
* Automatic retry mechanism
* Sensor validation checks
* Sensor recovery mechanism

### Temperature Breach Detection

* High temperature threshold:

```python
6.0°C
```

* Low temperature threshold:

```python
1.5°C
```

* Tracks continuous threshold violations
* Triggers alerts after prolonged exposure

---

### Blockchain Integration

Critical monitoring events are stored on blockchain:

* Alert events
* Recovery events
* Periodic system updates
* CSV file integrity hashes

Benefits:

* Immutable records
* Tamper resistance
* Transparent audit trail

---

### Telegram Notifications

Automatic alerts include:

* Temperature value
* Humidity value
* Breach type
* Breach duration
* Recovery notifications

---

### CSV Logging

Daily reports automatically generated:

```csv
timestamp,temperature,humidity,status
2026-06-20 10:30:00,5.4,62.1,NORMAL
2026-06-20 11:30:00,8.0,64.4,HIGH_ALERT
```

---

### File Integrity Verification

Daily reports are protected using:

```text
SHA-256 Hashing
```

Hash values are stored on blockchain to detect:

* Unauthorized modification
* Missing data
* Report tampering

---

## Technology Stack

| Component              | Technology       |
| ---------------------- | ---------------- |
| Hardware               | Raspberry Pi     |
| Sensor                 | DHT22            |
| Language               | Python           |
| Blockchain             | Web3.py          |
| Notifications          | Telegram Bot API |
| Data Storage           | CSV              |
| Logging                | Python Logging   |
| Integrity Verification | SHA-256          |
| Environment Variables  | dotenv           |

---

## Project Structure

```text
Temperature-Monitoring/

├── data/
│
├── csv/
│   ├── 2026-06-29.csv
│   └── ...
│
├── logs/
│   └── service.log
│
├── monitoring.py
│
├── .env
│
├── requirements.txt
│
├── README.md
│
└── LICENSE
```

---

## Installation

### Clone repository

```bash
git clone https://github.com/yourusername/temperature-monitoring.git

cd temperature-monitoring
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Required packages

```bash
pip install web3
pip install adafruit-circuitpython-dht
pip install python-dotenv
pip install requests
pip install RPi.GPIO
```

---

## Configuration

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token

TELEGRAM_CHAT_ID=your_chat_id

BLOCKCHAIN_URL=your_blockchain_rpc

PRIVATE_KEY=your_private_key
```

Update configuration values:

```python
ACCOUNT_ADDRESS="YOUR_WALLET_ADDRESS"

CONTRACT_ADDRESS="YOUR_CONTRACT_ADDRESS"
```

---

## Workflow

1. Initialize Raspberry Pi system
2. Start DHT22 sensor
3. Read temperature and humidity values
4. Detect threshold breaches
5. Log values to CSV
6. Trigger Telegram alerts if required
7. Store alert events on blockchain
8. Generate SHA256 report hash
9. Store hash on blockchain
10. Continue monitoring

---

## Blockchain Integration

Smart contract functions used:

```solidity
storeReading(
    int temperature,
    int humidity,
    string status
)

storeCSVHash(
    bytes32 fileHash,
    uint timestamp
)
```

Events recorded:

| Event            | Purpose                   |
| ---------------- | ------------------------- |
| ALERT_HIGH       | Critical high temperature |
| ALERT_LOW        | Critical low temperature  |
| NORMAL_RECOVERED | Recovery state            |
| PERIODIC_UPDATE  | Routine updates           |
| CSV_HASH         | File integrity            |

---

## Telegram Notifications

Example Alert:

```text
TEMPERATURE ALERT

Temperature: 8.2°C
Humidity: 67%

Breach Type: HIGH

Duration: 40 Minutes

Immediate action required
```

Recovery message:

```text
TEMPERATURE RETURNED TO NORMAL

Current Temperature: 4.2°C

System operating normally
```

---

## Future Improvements

Potential future enhancements:

* Dashboard interface
* Docker deployment
* MQTT integration
* Multiple sensor support
* Mobile application
* Machine learning anomaly detection
* IPFS report storage
* GPS integration
* Battery backup monitoring

---

## Licence

This project is released under the MIT License.


---

<p align="center">

<sub>IoT Monitoring + Blockchain + Real-Time Notifications</sub>

</p>
