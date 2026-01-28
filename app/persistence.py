#!/usr/bin/env python3
"""
Atomic JSON write utility for Seedkeeper.
Uses tmp+rename to prevent data corruption on crash.
"""

import json
import os
from pathlib import Path


def atomic_json_write(path, data, **kwargs):
    """Write JSON atomically using tmp file + os.replace()."""
    path = str(path)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, **kwargs)
    os.replace(tmp, path)
