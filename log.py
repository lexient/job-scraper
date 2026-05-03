import logging
import sys


_COLORS = {"WARN": "\033[33m", "ERROR": "\033[31m"}
_RESET = "\033[0m"
_USE_COLOR = sys.stdout.isatty()


class _Formatter(logging.Formatter):
    def format(self, record):
        if record.levelname == "WARNING":
            record.levelname = "WARN"
        line = super().format(record)
        if _USE_COLOR and record.levelname in _COLORS:
            return _COLORS[record.levelname] + line + _RESET
        return line


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_Formatter(fmt="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S"))

_logger = logging.getLogger("seek-match")
_logger.setLevel(logging.DEBUG)
_logger.addHandler(_handler)
_logger.propagate = False


def _fmt(args):
    return " ".join(str(a) for a in args)


def info(*args):
    _logger.info(_fmt(args))


def warn(*args):
    _logger.warning(_fmt(args))


def error(*args):
    _logger.error(_fmt(args))
