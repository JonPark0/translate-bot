import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = 'key_bot') -> logging.Logger:
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    # Get log level from environment
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Validate log level
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level_str not in valid_levels:
        print(f"Warning: Invalid LOG_LEVEL '{log_level_str}'. Using 'INFO'. Valid levels: {valid_levels}")
        log_level_str = 'INFO'
    
    log_level = getattr(logging, log_level_str)
    logger.setLevel(log_level)
    
    # Enhanced formatter with more details
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Log the current log level on startup
    if log_level_str != 'INFO':
        print(f"Logger initialized with level: {log_level_str}")
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    try:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        
        file_handler = RotatingFileHandler(
            logs_dir / 'key_bot.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    except PermissionError as e:
        console_handler.stream.write(f"Warning: Could not create log file due to permissions: {e}\n")
        console_handler.stream.write("Continuing with console logging only.\n")
    except Exception as e:
        console_handler.stream.write(f"Warning: Could not set up file logging: {e}\n")
        console_handler.stream.write("Continuing with console logging only.\n")
    
    return logger


def test_all_log_levels(logger: logging.Logger = None):
    """Test all logging levels to verify they work correctly."""
    if logger is None:
        logger = setup_logger('test_logger')
    
    logger.debug("🔍 DEBUG: This is a debug message - shows detailed diagnostic info")
    logger.info("ℹ️ INFO: This is an info message - general information")
    logger.warning("⚠️ WARNING: This is a warning message - something might be wrong")
    logger.error("❌ ERROR: This is an error message - something went wrong")
    logger.critical("🚨 CRITICAL: This is a critical message - system failure")
    
    # Additional test with formatting
    test_data = {"level": "test", "count": 5}
    logger.debug(f"Debug with data: {test_data}")
    logger.info(f"Info with formatting: Level={test_data['level']}, Count={test_data['count']}")


def get_log_level_info() -> dict:
    """Get information about current logging configuration."""
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Numeric levels for comparison
    level_values = {
        'DEBUG': 10,
        'INFO': 20, 
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }
    
    current_level_value = level_values.get(log_level_str, 20)
    
    # Determine which levels will be shown
    visible_levels = [level for level, value in level_values.items() if value >= current_level_value]
    hidden_levels = [level for level, value in level_values.items() if value < current_level_value]
    
    return {
        'current_level': log_level_str,
        'current_level_value': current_level_value,
        'visible_levels': visible_levels,
        'hidden_levels': hidden_levels,
        'all_levels': list(level_values.keys())
    }