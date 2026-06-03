import re

def _is_meaningful_message(content: str) -> bool:
    content = content.strip()
    if not content:
        return False
    
