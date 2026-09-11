import os
import re
import logging
from typing import Tuple, Dict, Any
from jinja2 import Template

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts"))

class PromptLoader:
    """Chargeur et moteur de rendu des prompts externalisés."""

    def __init__(self, prompts_dir: str = PROMPTS_DIR):
        self.prompts_dir = prompts_dir

    def load_and_render(self, prompt_name: str, **context) -> Tuple[str, str]:
        """
        Charge un fichier de prompt (ex: 'matching' ou 'matching.md'),
        sépare les sections SYSTEM et USER, et effectue le rendu Jinja2.
        
        Retourne : (system_instruction, user_prompt)
        """
        filename = prompt_name if prompt_name.endswith(".md") or prompt_name.endswith(".txt") else f"{prompt_name}.md"
        filepath = os.path.join(self.prompts_dir, filename)

        if not os.path.exists(filepath):
            # Fallback extension .txt
            txt_path = os.path.join(self.prompts_dir, f"{prompt_name}.txt")
            if os.path.exists(txt_path):
                filepath = txt_path
            else:
                logger.error(f"Fichier de prompt introuvable : {filepath}")
                raise FileNotFoundError(f"Fichier de prompt introuvable : {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            raw_content = f.read()

        system_instruction, user_template = self._parse_sections(raw_content)

        # Rendu Jinja2 pour la partie utilisateur
        rendered_user = Template(user_template).render(**context).strip()
        rendered_system = system_instruction.strip()

        return rendered_system, rendered_user

    def _parse_sections(self, content: str) -> Tuple[str, str]:
        """Extrait les blocs SYSTEM et USER délimités par # SYSTEM et # USER."""
        system_match = re.search(r'#+\s*SYSTEM\s*\n(.*?)(?=#+\s*USER|$)', content, re.DOTALL | re.IGNORECASE)
        user_match = re.search(r'#+\s*USER\s*\n(.*)$', content, re.DOTALL | re.IGNORECASE)

        system_part = system_match.group(1).strip() if system_match else ""
        user_part = user_match.group(1).strip() if user_match else content.strip()

        return system_part, user_part

prompt_loader = PromptLoader()
