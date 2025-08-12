import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = 'key_bot') -> logging.Logger:
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
    logger.setLevel(log_level)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
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