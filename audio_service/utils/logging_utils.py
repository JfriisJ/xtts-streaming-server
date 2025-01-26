import logging

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Konfigurerer og returnerer en logger med standardindstillinger.

    :param name: Navnet på loggeren.
    :param level: Logniveau (default INFO).
    :return: Logger-objekt.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
