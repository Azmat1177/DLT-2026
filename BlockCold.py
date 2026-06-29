import time
import board
import threading
import adafruit_dht
import os
import logging
from logging.handlers import RotatingFileHandler
import RPi.GPIO as GPIO
import signal
import sys
import requests
import json
import csv
from web3 import Web3
from datetime import datetime, timezone, timedelta  
from pathlib import Path
import socket
import hashlib
from dotenv import load_dotenv
load_dotenv() 

# Global state management
class SystemState:
    def __init__(self):
        self.managers = {
            'sensor': None,
            'csv': None,
            'blockchain': None,
            'telegram': None,
            'breach_tracker': None
        }
        self.initialized = False

# Create global state object
SYSTEM_STATE = SystemState()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


BLOCKCHAIN_URL = os.getenv('BLOCKCHAIN_URL', 'https://-etchain.org')
PRIVATE_KEY = os.getenv('PRIVATE_KEY', ' Add Here private key') # Either u Can access from the virtual Box

# Pin Definitions
DHT_PIN = 4

# Blockchain Configuration
ACCOUNT_ADDRESS = '' # Add your wallet address
CONTRACT_ADDRESS = '' # Add  Your Contract Address
# Contract ABI 
CONTRACT_ABI = [

	# Add your Contract ABI here

]

# Timing intervals (in seconds)
SENSOR_READ_INTERVAL =        # seconds
CSV_WRITE_INTERVAL =         # Write to CSV
BREACH_DURATION_THRESHOLD = # alert threshold
PERIODIC_BLOCKCHAIN_INTERVAL = # for periodic blockchain 
CSV_HASH_STORE_INTERVAL = #  for CSV hash storage
CSV_SEND_INTERVAL =         # for sending CSV via Telegram

# Temperature thresholds
TEMP_HIGH_CRITICAL = 6.0  # Upper critical threshold
TEMP_LOW_CRITICAL = 1.5   # Lower critical threshold

# Directory structure
BASE_DIR = "/home/pi/Temprature-Monitoring"
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_DIR = os.path.join(BASE_DIR, "csv")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Ensure all directories exist
for directory in [BASE_DIR, DATA_DIR, CSV_DIR, LOG_DIR]:
    Path(directory).mkdir(parents=True, exist_ok=True)

# System constants
MAX_BUFFER_SIZE = 1000
MAX_RETRIES = 3
BLOCKCHAIN_GAS_MULTIPLIER = 2
BLOCKCHAIN_CHAIN_ID = 42421
BLOCKCHAIN_GAS_LIMIT = 4000000

# GPIO Setup
GPIO.setmode(GPIO.BCM)

def cleanup(signum=None, frame=None):
    """Clean up resources before exiting"""
    logging.info("Starting cleanup process...")
    
    try:
        if SYSTEM_STATE.initialized:
            for manager_name, manager in SYSTEM_STATE.managers.items():
                if manager and hasattr(manager, 'cleanup'):
                    try:
                        manager.cleanup()
                        logging.info(f"{manager_name} cleaned up")
                    except Exception as e:
                        logging.error(f"Error cleaning up {manager_name}: {e}")
            
            # Additional GPIO cleanup
            GPIO.cleanup()
            
        logging.info("Cleanup completed")
        
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")
    finally:
        logging.info("System shutdown complete")
        sys.exit(0)

def setup_logging():
    """Configure logging with rotation and console output"""
    try:
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            
        log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, 'service.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(log_format)
        
        # Also add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        
        root.setLevel(logging.INFO)
        root.addHandler(file_handler)
        root.addHandler(console_handler)
        
        logging.info("Logging system initialized")
        
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        sys.exit(1)

def initialize_system():
    """Initialize all system components"""
    try:
        setup_logging()
        
        logging.info("Starting system initialization...")
        
        # Initialize sensor
        SYSTEM_STATE.managers['sensor'] = SensorManager()
        if not SYSTEM_STATE.managers['sensor'].sensor_ready:
            logging.error("Sensor initialization failed")
            return False
        
        # Initialize other managers
        SYSTEM_STATE.managers['csv'] = CSVManager()
        SYSTEM_STATE.managers['blockchain'] = BlockchainManager()
        SYSTEM_STATE.managers['telegram'] = TelegramManager(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CSV_DIR)
        SYSTEM_STATE.managers['breach_tracker'] = TemperatureBreachTracker()
        
        # Mark system as initialized
        SYSTEM_STATE.initialized = True
        logging.info("System initialization complete")
        
        return True
        
    except Exception as e:
        logging.error(f"System initialization failed: {e}")
        return False

class TemperatureBreachTracker:
    def __init__(self):
        self.breach_start_time = None
        self.is_in_breach = False
        self.breach_type = None
        self.alert_triggered = False
        self.breach_readings = []
        
    def check_temperature(self, temperature, humidity, current_time):
        """
        Monitor temperature and track 40-minute breach window
        Returns: (should_trigger_alert, should_send_recovery, status, breach_info)
        """
        is_outside_range = temperature >= TEMP_HIGH_CRITICAL or temperature <= TEMP_LOW_CRITICAL
        should_trigger_alert = False
        should_send_recovery = False
        status = "NORMAL"
        breach_info = None
        
        try:
            if is_outside_range:
                breach_type = "HIGH" if temperature >= TEMP_HIGH_CRITICAL else "LOW"
                
                # New breach or continuing breach
                if not self.is_in_breach:
                    # Start new breach tracking
                    self.breach_start_time = current_time
                    self.is_in_breach = True
                    self.breach_type = breach_type
                    self.alert_triggered = False
                    self.breach_readings = [(current_time, temperature, humidity)]
                    
                    logging.info(f"Temperature breach started: {temperature}°C ({breach_type})")
                    status = f"{breach_type}_MONITORING"
                    
                elif self.breach_type == breach_type:
                    # Continue tracking same breach
                    self.breach_readings.append((current_time, temperature, humidity))
                    breach_duration = current_time - self.breach_start_time
                    
                    # Check if 40 minutes have passed
                    if breach_duration >= BREACH_DURATION_THRESHOLD and not self.alert_triggered:
                        # Trigger alert sequence
                        should_trigger_alert = True
                        self.alert_triggered = True
                        status = f"{breach_type}_ALERT"
                        breach_info = {
                            'type': breach_type,
                            'duration': breach_duration,
                            'start_time': self.breach_start_time,
                            'readings': self.breach_readings
                        }
                        logging.warning(f"40-minute breach threshold reached! Temperature: {temperature}°C")
                    else:
                        remaining = BREACH_DURATION_THRESHOLD - breach_duration
                        status = f"{breach_type}_MONITORING"
                        if remaining > 0:
                            logging.info(f"Breach ongoing: {int(breach_duration/60)}min, {int(remaining/60)}min remaining")
                        
                else:
                    # Breach type changed - reset
                    self.breach_start_time = current_time
                    self.breach_type = breach_type
                    self.alert_triggered = False
                    self.breach_readings = [(current_time, temperature, humidity)]
                    status = f"{breach_type}_MONITORING"
                    
            else:
                # Temperature is normal
                if self.is_in_breach and self.alert_triggered:
                    # Recovery after alert was triggered
                    should_send_recovery = True
                    breach_duration = current_time - self.breach_start_time
                    breach_info = {
                        'type': self.breach_type,
                        'duration': breach_duration,
                        'start_time': self.breach_start_time,
                        'readings': self.breach_readings,
                        'recovery': True
                    }
                    logging.info(f"Temperature recovered to normal after {int(breach_duration/60)} minutes")
                
                # Reset breach tracking
                self.is_in_breach = False
                self.breach_start_time = None
                self.breach_type = None
                self.alert_triggered = False
                self.breach_readings = []
                status = "NORMAL"
                
            return should_trigger_alert, should_send_recovery, status, breach_info
            
        except Exception as e:
            logging.error(f"Breach tracking error: {e}")
            return False, False, "ERROR", None

class SensorManager:
    def __init__(self):
        self.sensor_ready = False
        self.dht_device = None
        
        try:
            logging.info(f"Initializing DHT22 sensor on GPIO{DHT_PIN}...")
            
            # Initialize DHT device
            self.dht_device = adafruit_dht.DHT22(getattr(board, f'D{DHT_PIN}'))
            
            # Test the sensor
            if self._test_sensor():
                logging.info("DHT sensor initialized successfully")
                self.sensor_ready = True
                
        except Exception as e:
            logging.error(f"DHT sensor initialization error: {e}")
            self.dht_device = None

    def _test_sensor(self):
        """Test sensor with multiple attempts"""
        if not self.dht_device:
            return False
            
        for attempt in range(5):
            try:
                time.sleep(3)
                temperature = self.dht_device.temperature
                humidity = self.dht_device.humidity
                
                if (temperature is not None and humidity is not None and 
                    -40 <= temperature <= 80 and 0 <= humidity <= 100):
                    logging.info(f"Sensor test successful: {temperature}°C, {humidity}%")
                    return True
                    
            except Exception as e:
                logging.warning(f"Sensor test attempt {attempt + 1} failed: {e}")
                
        return False

    def read_sensor(self):
        """Read sensor data with improved reliability"""
        if not self.dht_device:
            return None

        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                time.sleep(2)  # DHT22 needs time between reads
                
                temperature = self.dht_device.temperature
                humidity = self.dht_device.humidity

                if (temperature is not None and humidity is not None and 
                    -40 <= temperature <= 80 and 0 <= humidity <= 100):
                    
                    return {
                        'temperature': round(temperature, 1),
                        'humidity': round(humidity, 1),
                        'timestamp': time.time()
                    }
                    
            except RuntimeError as e:
                logging.warning(f"Sensor read attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                continue
                    
            except Exception as e:
                logging.error(f"Unexpected sensor error: {e}")
                break

        return None

    def cleanup(self):
        """Clean up sensor resources"""
        if self.dht_device:
            self.dht_device.exit()
            logging.info("Sensor cleanup completed")

class CSVManager:
    def __init__(self):
        self.current_file = None
        self.writer = None
        self.last_write_time = 0
        self.reading_count = 0
        self._create_daily_file()

    def _create_daily_file(self):
        """Create a new daily CSV file"""
        try:
            # Use date format for filename
            date_str = datetime.now().strftime("%Y-%m-%d")
            filepath = os.path.join(CSV_DIR, f"{date_str}.csv")
            
            # Check if file exists
            file_exists = os.path.exists(filepath)
            
            # Close existing file
            if self.current_file:
                self.current_file.close()
            
            # Open file
            self.current_file = open(filepath, 'a', newline='')
            self.writer = csv.writer(self.current_file)
            
            # Write headers if new file
            if not file_exists:
                self.writer.writerow(['timestamp', 'temperature', 'humidity', 'status'])
                self.current_file.flush()
            
            logging.info(f"CSV file ready: {filepath}")
            
        except Exception as e:
            logging.error(f"Error creating CSV file: {e}")

    def write_data(self, data, status):
        """Write data to CSV every 2nd reading (1 minute intervals)"""
        try:
            self.reading_count += 1
            
            # Write every 2nd reading (60 seconds interval)
            if self.reading_count % 2 == 0:
                # Check if we need a new daily file
                current_date = datetime.now().strftime("%Y-%m-%d")
                if self.current_file and current_date not in self.current_file.name:
                    self._create_daily_file()
                
                # Write data with precise timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.writer.writerow([
                    timestamp,
                    data['temperature'],
                    data['humidity'],
                    status
                ])
                
                self.current_file.flush()
                os.fsync(self.current_file.fileno())
                
                logging.info(f"Data written to CSV: {data['temperature']}°C, {data['humidity']}%, {status}")
                
        except Exception as e:
            logging.error(f"CSV write error: {e}")

    def get_current_csv_path(self):
        """Get the path of current CSV file"""
        if self.current_file:
            return self.current_file.name
        return None
    
    def calculate_csv_hash(self, file_path):
        """Calculate SHA-256 hash of CSV file"""
        try:
            if not os.path.exists(file_path):
                return None
                
            sha256_hash = hashlib.sha256()
            
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
                    
            # Return as hex string with 0x prefix for Web3
            return "0x" + sha256_hash.hexdigest()
            
        except Exception as e:
            logging.error(f"Error calculating hash: {e}")
            return None

    def cleanup(self):
        """Close CSV file"""
        try:
            if self.current_file:
                self.current_file.close()
                logging.info("CSV file closed")
        except Exception as e:
            logging.error(f"CSV cleanup error: {e}")

class BlockchainManager:
    def __init__(self):
        self.web3 = None
        self.contract = None
        self.last_periodic_upload = 0
        self.last_csv_hash_upload = 0
        
        try:
            self.web3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))
            if self.web3.is_connected():
                self.contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
                    abi=CONTRACT_ABI
                )
                # Set up account
                self.account = Web3.to_checksum_address(ACCOUNT_ADDRESS)
                self.web3.eth.default_account = self.account
                logging.info(f"Blockchain connected to {BLOCKCHAIN_URL}")
                logging.info(f"Contract address: {CONTRACT_ADDRESS}")
            else:
                logging.error("Blockchain connection failed")
                
        except Exception as e:
            logging.error(f"Blockchain init error: {e}")

    def _send_transaction(self, function):
        """Helper method to build and send transactions"""
        try:
            # Get current gas price
            gas_price = self.web3.eth.gas_price
            
            # Build transaction
            transaction = function.build_transaction({
                'from': self.account,
                'gas': BLOCKCHAIN_GAS_LIMIT,
                'gasPrice': gas_price * BLOCKCHAIN_GAS_MULTIPLIER,
                'nonce': self.web3.eth.get_transaction_count(self.account),
                'chainId': BLOCKCHAIN_CHAIN_ID
            })
            
            # Sign transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, PRIVATE_KEY)
            
            # Send transaction - try both attribute names for compatibility
            try:
                # Newer versions of web3.py
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            except AttributeError:
                # Older versions use 'raw_transaction'
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            # Wait for receipt (with timeout)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if tx_receipt.status == 1:
                logging.info(f"Transaction successful: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                logging.error("Transaction failed")
                return None
                
        except Exception as e:
            logging.error(f"Transaction error: {e}")
            return None

    def send_alert_to_blockchain(self, temperature, humidity, breach_type):
        """Send alert to blockchain"""
        try:
            if not self.contract or not self.web3.is_connected():
                logging.error("Blockchain not connected")
                return None
                
            logging.info(f"Sending alert to blockchain: {temperature}°C, {breach_type}")
            
            # Convert to integer (multiply by 10 to preserve 1 decimal)
            temp_int = int(temperature * 10)
            humidity_int = int(humidity * 10)
            status = f"ALERT_{breach_type}"
            
            # Call storeReading function
            function = self.contract.functions.storeReading(
                temp_int,
                humidity_int,
                status
            )
            
            return self._send_transaction(function)
            
        except Exception as e:
            logging.error(f"Blockchain alert error: {e}")
            return None

    def send_recovery_to_blockchain(self, temperature, humidity):
        """Send recovery status to blockchain"""
        try:
            if not self.contract or not self.web3.is_connected():
                return None
                
            logging.info(f"Sending recovery to blockchain: {temperature}°C")
            
            temp_int = int(temperature * 10)
            humidity_int = int(humidity * 10)
            
            function = self.contract.functions.storeReading(
                temp_int,
                humidity_int,
                "NORMAL_RECOVERED"
            )
            
            return self._send_transaction(function)
            
        except Exception as e:
            logging.error(f"Blockchain recovery error: {e}")
            return None

    def send_periodic_update(self, temperature, humidity):
        """Send periodic update every 11 hours"""
        try:
            if not self.contract or not self.web3.is_connected():
                return False
                
            current_time = time.time()
            
            if current_time - self.last_periodic_upload >= PERIODIC_BLOCKCHAIN_INTERVAL:
                logging.info(f"Sending periodic update to blockchain: {temperature}°C")
                
                temp_int = int(temperature * 10)
                humidity_int = int(humidity * 10)
                
                function = self.contract.functions.storeReading(
                    temp_int,
                    humidity_int,
                    "PERIODIC_UPDATE"
                )
                
                tx_hash = self._send_transaction(function)
                if tx_hash:
                    self.last_periodic_upload = current_time
                    return True
                
            return False
            
        except Exception as e:
            logging.error(f"Periodic update error: {e}")
            return False

    def store_csv_hash(self, csv_hash, timestamp):
        """Store CSV hash on blockchain every 24 hours"""
        try:
            if not self.contract or not self.web3.is_connected():
                return False
                
            current_time = time.time()
            
            if current_time - self.last_csv_hash_upload >= CSV_HASH_STORE_INTERVAL:
                logging.info(f"Storing CSV hash on blockchain: {csv_hash[:10]}...")
                
                # Convert hex string to bytes32
                hash_bytes = Web3.to_bytes(hexstr=csv_hash)
                
                function = self.contract.functions.storeCSVHash(
                    hash_bytes,
                    int(timestamp)
                )
                
                tx_hash = self._send_transaction(function)
                if tx_hash:
                    self.last_csv_hash_upload = current_time
                    return True
                
            return False
            
        except Exception as e:
            logging.error(f"CSV hash storage error: {e}")
            return False

    def cleanup(self):
        """Clean up blockchain resources"""
        logging.info("Blockchain cleanup completed")

class TelegramManager:
    def __init__(self, token, chat_id, csv_dir):
        self.token = token
        self.chat_id = chat_id
        self.csv_dir = csv_dir
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_csv_send = 0

    def send_alert_notification(self, temperature, humidity, breach_type, duration):
        """Send alert notification to Telegram"""
        try:
            message = f""" TEMPERATURE ALERT - VISIT DEVICE-A!

Temperature: {temperature:.1f}°C
Humidity: {humidity:.1f}%
Breach Type: {breach_type}
Duration: {int(duration/60)} minutes
Threshold: {'>' if breach_type == 'HIGH' else '<'} {TEMP_HIGH_CRITICAL if breach_type == 'HIGH' else TEMP_LOW_CRITICAL}°C
Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}

 IMMEDIATE ACTION REQUIRED!
Alert sequence activated: Blockchain notification sent """
            
            return self._send_message(message)
            
        except Exception as e:
            logging.error(f"Failed to send alert notification: {e}")
            return False

    def send_recovery_notification(self, temperature, humidity, breach_type, duration):
        """Send recovery notification to Telegram"""
        try:
            hours, remainder = divmod(int(duration), 3600)
            minutes = remainder // 60
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            message = f""" TEMPERATURE RETURNED TO NORMAL DEVICE-A

Current Temperature: {temperature:.1f}°C
Current Humidity: {humidity:.1f}%
Previous Breach Type: {breach_type}
Total Breach Duration: {duration_str}
Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}

System has returned to normal operation.
Recovery status recorded on blockchain."""
            
            return self._send_message(message)
            
        except Exception as e:
            logging.error(f"Failed to send recovery notification: {e}")
            return False

    def _send_message(self, message):
        """Send text message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            response = requests.post(
                url,
                data={
                    "chat_id": self.chat_id,
                    "text": message
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logging.info("Telegram message sent successfully")
                return True
            else:
                logging.error(f"Telegram API error: {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Telegram send error: {e}")
            return False

    def send_daily_csv(self):
        """Send daily CSV file to Telegram every 24 hours"""
        try:
            current_time = time.time()
            
            # Check if 24 hours have passed since last send
            if current_time - self.last_csv_send < CSV_SEND_INTERVAL:
                return False
            
            # Get today's CSV file
            today = datetime.now().strftime("%Y-%m-%d")
            csv_path = os.path.join(self.csv_dir, f"{today}.csv")
            
            # If today's file doesn't exist or is empty, try yesterday's
            if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                csv_path = os.path.join(self.csv_dir, f"{yesterday}.csv")
                
            if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
                logging.warning("No CSV file to send")
                return False
            
            # Calculate hash for integrity verification
            csv_hash = SYSTEM_STATE.managers['csv'].calculate_csv_hash(csv_path)
            
            # Send file with detailed caption
            caption = f""" Daily Temperature Report
Date: {os.path.basename(csv_path).replace('.csv', '')}
Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
File Hash: {csv_hash[:10]}... (stored on blockchain)
Temperature Range: {TEMP_LOW_CRITICAL}°C to {TEMP_HIGH_CRITICAL}°C 
"""
            
            if self._send_document(csv_path, caption):
                self.last_csv_send = current_time
                
                # Store hash on blockchain for integrity verification
                if SYSTEM_STATE.managers['blockchain']:
                    SYSTEM_STATE.managers['blockchain'].store_csv_hash(csv_hash, int(current_time))
                
                logging.info(f"Daily CSV sent successfully: {csv_path}")
                return True
                
        except Exception as e:
            logging.error(f"Daily CSV send error: {e}")
            
        return False

    def _send_document(self, file_path, caption):
        """Send document to Telegram"""
        try:
            url = f"{self.base_url}/sendDocument"
            
            with open(file_path, 'rb') as file:
                files = {'document': (os.path.basename(file_path), file, 'text/csv')}
                data = {'chat_id': self.chat_id, 'caption': caption}
                
                response = requests.post(url, data=data, files=files, timeout=30)
                
                if response.status_code == 200:
                    return True
                else:
                    logging.error(f"Telegram document send failed: {response.text}")
                    return False
                    
        except Exception as e:
            logging.error(f"Document send error: {e}")
            return False

    def cleanup(self):
        """Clean up Telegram resources"""
        logging.info("Telegram cleanup completed")

def trigger_alert_sequence(temperature, humidity, breach_info):
    """Execute the complete alert sequence for 40-minute breach"""
    try:
        logging.warning(f"TRIGGERING ALERT SEQUENCE for 40-minute breach!")
        
        # 1. Send to blockchain with retry mechanism
        if SYSTEM_STATE.managers['blockchain']:
            for attempt in range(3):  # Try 3 times
                tx_hash = SYSTEM_STATE.managers['blockchain'].send_alert_to_blockchain(
                    temperature, humidity, breach_info['type']
                )
                if tx_hash:
                    logging.info(f"Alert sent to blockchain: {tx_hash}")
                    break
                else:
                    logging.warning(f"Blockchain send attempt {attempt + 1} failed")
                    time.sleep(5)
        
        # 2. Send Telegram notification
        if SYSTEM_STATE.managers['telegram']:
            SYSTEM_STATE.managers['telegram'].send_alert_notification(
                temperature, humidity, breach_info['type'], breach_info['duration']
            )
        
        logging.info("Alert sequence completed")
        
    except Exception as e:
        logging.error(f"Alert sequence error: {e}")

def send_recovery_notifications(temperature, humidity, breach_info):
    """Send recovery notifications to blockchain and Telegram"""
    try:
        logging.info("Sending recovery notifications...")
        
        # Send to blockchain with retry
        if SYSTEM_STATE.managers['blockchain']:
            for attempt in range(3):
                tx_hash = SYSTEM_STATE.managers['blockchain'].send_recovery_to_blockchain(
                    temperature, humidity
                )
                if tx_hash:
                    logging.info(f"Recovery sent to blockchain: {tx_hash}")
                    break
                else:
                    logging.warning(f"Recovery blockchain send attempt {attempt + 1} failed")
                    time.sleep(3)
        
        # Send to Telegram
        if SYSTEM_STATE.managers['telegram']:
            SYSTEM_STATE.managers['telegram'].send_recovery_notification(
                temperature, humidity, breach_info['type'], breach_info['duration']
            )
        
        logging.info("Recovery notifications sent")
        
    except Exception as e:
        logging.error(f"Recovery notification error: {e}")

def main():
    """Main monitoring loop"""
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        # Initialize system
        if not initialize_system():
            logging.error("System initialization failed")
            sys.exit(1)
        
        logging.info("Starting main monitoring loop...")
        logging.info(f"Temperature thresholds: {TEMP_LOW_CRITICAL}°C - {TEMP_HIGH_CRITICAL}°C")
        logging.info(f"Sensor read interval: {SENSOR_READ_INTERVAL}s")
        logging.info(f"CSV write interval: Every 2nd reading ({CSV_WRITE_INTERVAL}s)")
        logging.info(f"Breach alert threshold: {BREACH_DURATION_THRESHOLD/60} minutes")
        
        # Get manager references
        sensor_mgr = SYSTEM_STATE.managers['sensor']
        csv_mgr = SYSTEM_STATE.managers['csv']
        breach_tracker = SYSTEM_STATE.managers['breach_tracker']
        blockchain_mgr = SYSTEM_STATE.managers['blockchain']
        telegram_mgr = SYSTEM_STATE.managers['telegram']
        
        # Timing variables
        last_sensor_read = 0
        last_daily_tasks = 0
        last_blockchain_check = 0
        blockchain_check_interval = 300  # Check connection every 5 minutes
        
        # System status variables
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:
            try:
                current_time = time.time()
                
                # Periodic blockchain connection check
                if blockchain_mgr and current_time - last_blockchain_check >= blockchain_check_interval:
                    try:
                        if not blockchain_mgr.web3.is_connected():
                            logging.warning("Blockchain connection lost, attempting reconnect...")
                            blockchain_mgr.web3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))
                            if blockchain_mgr.web3.is_connected():
                                blockchain_mgr.contract = blockchain_mgr.web3.eth.contract(
                                    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
                                    abi=CONTRACT_ABI
                                )
                                blockchain_mgr.web3.eth.default_account = blockchain_mgr.account
                                logging.info("Blockchain reconnected successfully")
                            else:
                                logging.error("Failed to reconnect to blockchain")
                    except Exception as e:
                        logging.error(f"Blockchain reconnection error: {e}")
                    
                    last_blockchain_check = current_time
                
                # Read sensor every 30 seconds
                if current_time - last_sensor_read >= SENSOR_READ_INTERVAL:
                    sensor_data = sensor_mgr.read_sensor()
                    
                    if sensor_data:
                        temperature = sensor_data['temperature']
                        humidity = sensor_data['humidity']
                        
                        # Reset error counter on successful read
                        consecutive_errors = 0
                        
                        # Check temperature breach status
                        should_alert, should_recover, status, breach_info = breach_tracker.check_temperature(
                            temperature, humidity, current_time
                        )
                        
                        # Write to CSV every 2nd reading (1 minute intervals)
                        csv_mgr.write_data(sensor_data, status)
                        
                        # Handle 40-minute breach alert
                        if should_alert and breach_info:
                            trigger_alert_sequence(temperature, humidity, breach_info)
                        
                        # Handle recovery after alert was triggered
                        if should_recover and breach_info:
                            send_recovery_notifications(temperature, humidity, breach_info)
                        
                        # Send periodic update to blockchain every 11 hours
                        if blockchain_mgr and blockchain_mgr.web3.is_connected():
                            blockchain_mgr.send_periodic_update(temperature, humidity)
                        
                        # Log status with blockchain connection info
                        bc_status = "BC:Connected" if (blockchain_mgr and blockchain_mgr.web3.is_connected()) else "BC:Disconnected"
                        logging.info(f"Reading: {temperature}°C, {humidity}%, Status: {status}, {bc_status}")
                        
                    else:
                        consecutive_errors += 1
                        logging.error(f"Failed to read sensor (consecutive errors: {consecutive_errors})")
                        
                        # If too many consecutive errors, attempt sensor reset
                        if consecutive_errors >= max_consecutive_errors:
                            logging.error("Too many sensor errors, attempting reset...")
                            try:
                                sensor_mgr.cleanup()
                                time.sleep(5)
                                sensor_mgr.__init__()
                                consecutive_errors = 0
                            except Exception as e:
                                logging.error(f"Sensor reset failed: {e}")
                    
                    last_sensor_read = current_time
                
                # Daily tasks (CSV hash storage and Telegram sending)
                if current_time - last_daily_tasks >= 3600:  # Check every hour
                    try:
                        # Send daily CSV to Telegram (checks 24h internally)
                        telegram_mgr.send_daily_csv()
                    except Exception as e:
                        logging.error(f"Daily tasks error: {e}")
                    
                    last_daily_tasks = current_time
                
                # Small delay to prevent CPU overload
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                logging.info("Shutdown requested by user")
                break
                
            except Exception as e:
                logging.error(f"Main loop error: {e}")
                time.sleep(5)
                
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        
    finally:
        logging.info("Shutting down system...")
        cleanup()

if __name__ == "__main__":
    main()
