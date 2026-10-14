#!/usr/bin/env python
"""Utilidad de línea de comandos de Django."""

import os
import sys


def main() -> None:
    # En la máquina de cada integrante se trabaja con los settings de
    # desarrollo. La integración continua y producción definen
    # DJANGO_SETTINGS_MODULE explícitamente.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
