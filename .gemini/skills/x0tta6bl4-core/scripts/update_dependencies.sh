#!/bin/bash
set -euo pipefail

pip install --upgrade \
  "aiohttp>=3.13.3" \
  "certifi>=2024.7.4" \
  "paramiko>=3.4.0" \
  "Jinja2>=3.1.6" \
  "pillow>=10.3.0" \
  "setuptools>=78.1.1" \
  "urllib3>=2.6.3" \
  "python-multipart>=0.0.22" \
  "filelock>=3.20.3" \
  "configobj>=5.0.9" \
  "pip>=25.3"
