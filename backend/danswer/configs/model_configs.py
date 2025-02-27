import os
from enum import Enum

from danswer.configs.constants import DanswerGenAIModel
from danswer.configs.constants import ModelHostType

# Important considerations when choosing models
# Max tokens count needs to be high considering use case (at least 512)
# Models used must be MIT or Apache license
# Inference/Indexing speed

# https://www.sbert.net/docs/pretrained_models.html
# Use 'multi-qa-MiniLM-L6-cos-v1' if license is added because it is 3x faster (384 dimensional embedding)
# Context size is 256 for above though
DOCUMENT_ENCODER_MODEL = "sentence-transformers/all-distilroberta-v1"
DOC_EMBEDDING_DIM = 768  # Depends on the document encoder model

# https://www.sbert.net/docs/pretrained-models/ce-msmarco.html
# Previously using "cross-encoder/ms-marco-MiniLM-L-6-v2" alone
CROSS_ENCODER_MODEL_ENSEMBLE = [
    "cross-encoder/ms-marco-MiniLM-L-4-v2",
    "cross-encoder/ms-marco-TinyBERT-L-2-v2",
]

# Better to keep it loose, surfacing more results better than missing results
SEARCH_DISTANCE_CUTOFF = 0.1  # Cosine similarity (currently), range of -1 to 1 with -1 being completely opposite

QUERY_MAX_CONTEXT_SIZE = 256
# The below is correlated with CHUNK_SIZE in app_configs but not strictly calculated
# To avoid extra overhead of tokenizing for chunking during indexing.
DOC_EMBEDDING_CONTEXT_SIZE = 512
CROSS_EMBED_CONTEXT_SIZE = 512

# Purely an optimization, memory limitation consideration
BATCH_SIZE_ENCODE_CHUNKS = 8


#####
# Generative AI Model Configs
#####
# Other models should work as well, check the library/API compatibility.
# But these are the models that have been verified to work with the existing prompts.
# Using a different model may require some prompt tuning. See qa_prompts.py
VERIFIED_MODELS = {
    DanswerGenAIModel.OPENAI: ["text-davinci-003"],
    DanswerGenAIModel.OPENAI_CHAT: ["gpt-3.5-turbo", "gpt-4"],
    DanswerGenAIModel.GPT4ALL: ["ggml-model-gpt4all-falcon-q4_0.bin"],
    DanswerGenAIModel.GPT4ALL_CHAT: ["ggml-model-gpt4all-falcon-q4_0.bin"],
    # The "chat" model below is actually "instruction finetuned" and does not support conversational
    DanswerGenAIModel.HUGGINGFACE.value: ["meta-llama/Llama-2-70b-chat-hf"],
    DanswerGenAIModel.HUGGINGFACE_CHAT.value: ["meta-llama/Llama-2-70b-hf"],
}

# Sets the internal Danswer model class to use
INTERNAL_MODEL_VERSION = os.environ.get(
    "INTERNAL_MODEL_VERSION", DanswerGenAIModel.OPENAI_CHAT.value
)

# If the Generative AI model requires an API key for access, otherwise can leave blank
GEN_AI_API_KEY = os.environ.get("GEN_AI_API_KEY", "")

# If using GPT4All or OpenAI, specify the model version
GEN_AI_MODEL_VERSION = os.environ.get(
    "GEN_AI_MODEL_VERSION",
    VERIFIED_MODELS.get(DanswerGenAIModel(INTERNAL_MODEL_VERSION), [""])[0],
)

# If the Generative Model is hosted to accept requests (DanswerGenAIModel.REQUEST) then
# set the two below to specify
# - Where to hit the endpoint
# - How should the request be formed
GEN_AI_ENDPOINT = os.environ.get("GEN_AI_ENDPOINT", "")
GEN_AI_HOST_TYPE = os.environ.get("GEN_AI_HOST_TYPE", ModelHostType.HUGGINGFACE.value)

# Set this to be enough for an answer + quotes
GEN_AI_MAX_OUTPUT_TOKENS = int(os.environ.get("GEN_AI_MAX_OUTPUT_TOKENS", "512"))

# Danswer custom Deep Learning Models
INTENT_MODEL_VERSION = "danswer/intent-model"
