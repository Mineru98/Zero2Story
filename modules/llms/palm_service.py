import os
import threading
import toml
from pathlib import Path
import google.generativeai as palm_api

from pingpong import PingPong
from pingpong.pingpong import PPManager
from pingpong.pingpong import PromptFmt
from pingpong.pingpong import UIFmt
from pingpong.gradio import GradioChatUIFmt

from modules.llms import (
    LLMFactory,
    PromptFmt, PromptManager, PPManager, UIPPManager, LLMService
)

class PaLMFactory(LLMFactory):
    _palm_api_key = None

    def __init__(self, palm_api_key=None):
        if not PaLMFactory._palm_api_key:
            PaLMFactory.load_palm_api_key()
            assert PaLMFactory._palm_api_key, "PaLM API Key is missing."
            palm_api.configure(api_key=PaLMFactory._palm_api_key)

    def create_prompt_format(self):
        return PaLMChatPromptFmt()

    def create_prompt_manager(self, prompts_path: str=None):
        return PaLMPromptManager((prompts_path or Path('.') / 'prompts' / 'palm_prompts.toml'))
    
    def create_pp_manager(self):
        return PaLMChatPPManager()

    def create_ui_pp_manager(self):
        return GradioPaLMChatPPManager()
    
    def create_llm_service(self):
        return PaLMService()
    
    @classmethod
    def load_palm_api_key(cls, palm_api_key: str=None):
        if palm_api_key:
            cls._palm_api_key = palm_api_key
        else:
            palm_api_key = os.getenv("PALM_API_KEY")

            if palm_api_key is None:
                with open('.palm_api_key.txt', 'r') as file:
                    palm_api_key = file.read().strip()

            if not palm_api_key:
                raise ValueError("PaLM API Key is missing.")
            cls._palm_api_key = palm_api_key
    
    @property
    def palm_api_key(self):
        return PaLMFactory._palm_api_key
    
    @palm_api_key.setter
    def palm_api_key(self, palm_api_key: str):
        assert palm_api_key, "PaLM API Key is missing."
        PaLMFactory._palm_api_key = palm_api_key
        palm_api.configure(api_key=PaLMFactory._palm_api_key)


class PaLMChatPromptFmt(PromptFmt):
    @classmethod
    def ctx(cls, context):
        pass

    @classmethod
    def prompt(cls, pingpong, truncate_size):
        ping = pingpong.ping[:truncate_size]
        pong = pingpong.pong
        
        if pong is None or pong.strip() == "":
            return [
                {
                    "author": "USER",
                    "content": ping
                },
            ]
        else:
            pong = pong[:truncate_size]

            return [
                {
                    "author": "USER",
                    "content": ping
                },
                {
                    "author": "AI",
                    "content": pong
                },
            ]


class PaLMPromptManager(PromptManager):
    _instance = None
    _lock = threading.Lock()
    _prompts = None

    def __new__(cls, prompts_path):
        if cls._instance is None:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(PaLMPromptManager, cls).__new__(cls)
                    cls._instance.load_prompts(prompts_path)
        return cls._instance

    def load_prompts(self, prompts_path):
        self._prompts_path = prompts_path
        self.reload_prompts()

    def reload_prompts(self):
        assert self.prompts_path, "Prompt path is missing."
        self._prompts = toml.load(self.prompts_path)

    @property
    def prompts_path(self):
        return self._prompts_path
    
    @prompts_path.setter
    def prompts_path(self, prompts_path):
        self._prompts_path = prompts_path
        self.reload_prompts()

    @property
    def prompts(self):
        if self._prompts is None:
            self.load_prompts()
        return self._prompts


class PaLMChatPPManager(PPManager):
    def build_prompts(self, from_idx: int=0, to_idx: int=-1, fmt: PromptFmt=None, truncate_size: int=None):
        if fmt is None:
            factory = PaLMFactory()
            fmt = factory.create_prompt_format()
        
        results = []
        
        if to_idx == -1 or to_idx >= len(self.pingpongs):
            to_idx = len(self.pingpongs)

        for idx, pingpong in enumerate(self.pingpongs[from_idx:to_idx]):
            results += fmt.prompt(pingpong, truncate_size=truncate_size)

        return results


class GradioPaLMChatPPManager(UIPPManager, PaLMChatPPManager):
    def build_uis(self, from_idx: int=0, to_idx: int=-1, fmt: UIFmt=GradioChatUIFmt):
        if to_idx == -1 or to_idx >= len(self.pingpongs):
            to_idx = len(self.pingpongs)

        results = []

        for pingpong in self.pingpongs[from_idx:to_idx]:
            results.append(fmt.ui(pingpong))

        return results 

class PaLMService(LLMService):
    async def gen_text(
        self,
        prompt,
        mode="chat", #chat or text
        parameters=None,
        use_filter=True
    ):
        if parameters is None:
            temperature = 1.0
            top_k = 40
            top_p = 0.95
            max_output_tokens = 1024
            
            # default safety settings
            safety_settings = [{"category":"HARM_CATEGORY_DEROGATORY","threshold":1},
                            {"category":"HARM_CATEGORY_TOXICITY","threshold":1},
                            {"category":"HARM_CATEGORY_VIOLENCE","threshold":2},
                            {"category":"HARM_CATEGORY_SEXUAL","threshold":2},
                            {"category":"HARM_CATEGORY_MEDICAL","threshold":2},
                            {"category":"HARM_CATEGORY_DANGEROUS","threshold":2}]
            if not use_filter:
                for idx, _ in enumerate(safety_settings):
                    safety_settings[idx]['threshold'] = 4

            if mode == "chat":
                parameters = {
                    'model': 'models/chat-bison-001',
                    'candidate_count': 1,
                    'context': "",
                    'temperature': temperature,
                    'top_k': top_k,
                    'top_p': top_p,
                    'safety_settings': safety_settings,
                }
            else:
                parameters = {
                    'model': 'models/text-bison-001',
                    'candidate_count': 1,
                    'temperature': temperature,
                    'top_k': top_k,
                    'top_p': top_p,
                    'max_output_tokens': max_output_tokens,
                    'safety_settings': safety_settings,
                }

        try:
            if mode == "chat":
                response = await palm_api.chat_async(**parameters, messages=prompt)
            else:
                response = palm_api.generate_text(**parameters, prompt=prompt)
        except:
            raise EnvironmentError("PaLM API is not available.")

        if use_filter and len(response.filters) > 0:
            raise Exception("PaLM API has withheld a response due to content safety concerns.")
        else:
            if mode == "chat":
                response_txt = response.last
            else:
                response_txt = response.result
        
        return response, response_txt