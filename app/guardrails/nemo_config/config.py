import os
from langchain_groq import ChatGroq
from nemoguardrails.llm.providers import register_llm_provider

class EnvChatGroq(ChatGroq):
    """Custom wrapper to ensure Groq accepts the firewall-specific API key from config.yml"""
    def __init__(self, **kwargs):
        # 1. Directly grab your secrets from the Docker environment
        firewall_key = os.environ.get("FIREWALL_GROQ_API_KEY")
        firewall_model = os.environ.get("FIREWALL_MODEL")
        
        # 2. Force LangChain to use them using the exact parameter names it expects
        if firewall_key:
            kwargs["groq_api_key"] = firewall_key
            
        if firewall_model:
            kwargs["model_name"] = firewall_model
            
        # 3. Clean the previous key
        kwargs.pop("api_key", None)
        kwargs.pop("model", None)

        super().__init__(**kwargs)

# Register our custom wrapper as a provider named "groq"
register_llm_provider("groq", EnvChatGroq)









# annoy stands for Approximate Nearest Neighbors Oh Yeah.

# It's a highly efficient library written in C++ that specializes in one thing: finding the most similar items in a large dataset very, very quickly. In the world of AI, "items" are usually vectors (long lists of numbers that represent text).

# Crucially, annoy is NOT searching through your PDF documents in Qdrant. It's only checking against the small list of safety rules you defined.




# 1. The Environment Variables (.env)
# When Docker starts your server, it loads your .env file into the system's hidden environment. At this point, the server knows that $FIREWALL_GROQ_API_KEY equals gsk_eUzTR....

# 2. NeMo Guardrails Reads config.yml
# When the NeMo Guardrails engine boots up, it reads your config.yml file and sees this:

# yaml


#     parameters:
#       api_key: $FIREWALL_GROQ_API_KEY
#       model: $FIREWALL_MODEL
# NeMo sees the $ symbols and says, "Ah! I need to replace these with the actual values from the .env file." It replaces them, bundles them into a Python dictionary, and passes that dictionary into our EnvChatGroq class as **kwargs (which stands for Keyword Arguments).

# So when __init__(self, **kwargs) is called, kwargs secretly looks like this inside Python:

# python


# kwargs = {
#     "api_key": "gsk_eUzTR...",
#     "model": "mixtral-8x7b-32768",
#     "temperature": 0.1
# }
# 3. Our Custom Wrapper intercepts the Dictionary
# Here is where our code kicks in. LangChain's ChatGroq class expects the dictionary keys to be named exactly "groq_api_key" and "model_name".

# So we use the .pop() function. In Python dictionaries, .pop("api_key") does two things at the exact same time:

# It deletes "api_key" from the dictionary.
# It grabs the value ("gsk_eUzTR...") so we can assign it to a brand new key.
# By running:

# python


# kwargs["groq_api_key"] = kwargs.pop("api_key")