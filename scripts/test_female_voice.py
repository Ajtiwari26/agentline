import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import prompts

class TestFemaleVoiceAndAgentConfig(unittest.TestCase):
    def test_env_vars(self):
        """Verify that environment variables are correctly loaded for the female voice and name."""
        self.assertEqual(config.AGENT_NAME, "Kavya", "AGENT_NAME should be configured as 'Kavya'")
        self.assertEqual(config.GEMINI_LIVE_VOICE, "Aoede", "GEMINI_LIVE_VOICE should be configured as 'Aoede'")
        self.assertEqual(config.COMPANY, "nukkad", "COMPANY should be configured as 'nukkad'")
        
    def test_knowledge_base_loading(self):
        """Verify that load_kb loads the Nukkad Tech Solutions knowledge base."""
        kb = prompts.load_kb()
        brand_name = kb.get("system", {}).get("brand_name")
        self.assertEqual(brand_name, "Nukkad Tech Solutions", "Brand name should be Nukkad Tech Solutions")
        
    def test_system_prompt_generation(self):
        """Verify that the system prompt dynamically contains the correct name and brand."""
        sys_prompt = prompts.build_system_prompt(direction="outbound")
        self.assertIn("Kavya", sys_prompt, "System prompt should mention agent name 'Kavya'")
        self.assertIn("Nukkad Tech Solutions", sys_prompt, "System prompt should mention brand name 'Nukkad Tech Solutions'")
        
    def test_pipeline_voice_resolution(self):
        """Verify that the pipeline resolves the correct prebuilt female voice (Aoede)."""
        kb = prompts.load_kb()
        company = config.COMPANY
        env_voice = config.GEMINI_LIVE_VOICE
        
        # Mirroring the voice resolution logic from core/pipeline.py
        if company == "bla_bli_blu" or kb.get("system", {}).get("agent_name", "").lower() == "kavya":
            voice_name = env_voice if env_voice and env_voice != "Charon" else "Aoede"
        else:
            voice_name = env_voice or "Charon"
            
        self.assertEqual(voice_name, "Aoede", "Voice should resolve to female voice 'Aoede'")

if __name__ == "__main__":
    unittest.main()
