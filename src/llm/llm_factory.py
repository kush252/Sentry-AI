import os
import time
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

class RateLimitedLLM:
    """Wraps the LLM to enforce hard wait times for Google free tier rate limits."""
    def __init__(self, llm):
        self._llm = llm
        
    def __getattr__(self, name):
        return getattr(self._llm, name)
        
    def invoke(self, *args, **kwargs):
        for attempt in range(5):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print(f"[*] Gemini API rate limit reached. Sleeping 70s... (Attempt {attempt+1}/5)")
                    time.sleep(70)
                else:
                    raise e
        return self._llm.invoke(*args, **kwargs)
        
    def with_structured_output(self, *args, **kwargs):
        structured_runnable = self._llm.with_structured_output(*args, **kwargs)
        
        class RateLimitedRunnable:
            def __init__(self, runnable):
                self._runnable = runnable
                
            def invoke(self, *args2, **kwargs2):
                for attempt in range(5):
                    try:
                        return self._runnable.invoke(*args2, **kwargs2)
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            print(f"\n[*] Gemini API rate limit reached. Sleeping 70s... (Attempt {attempt+1}/5)")
                            time.sleep(70)
                        else:
                            raise e
                return self._runnable.invoke(*args2, **kwargs2)
                
        return RateLimitedRunnable(structured_runnable)

def get_llm(model_name: str = "gemini-2.5-flash") -> BaseChatModel:
    """
    Returns a generic LangChain BaseChatModel.
    """
    if "gemini" in model_name.lower():
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
            
        llm = ChatGoogleGenerativeAI(
            model=model_name, 
            google_api_key=api_key,
            max_retries=10
        )
        return RateLimitedLLM(llm)
    
    raise ValueError(f"Unsupported model: {model_name}")
