"""Garante que o pacote do bot esteja importável nos testes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
