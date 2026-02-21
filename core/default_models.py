"""Default models for various providers."""

DEFAULT_MODELS = {
    "openrouter": {
        "text": [
            {
                "id": "meta-llama/llama-3.3-70b-instruct",
                "display_name": "Llama 3.3 70B Instruct",
                "context_length": 128000,
                "notes": "Strong generalist, good tool calling, open weights (Meta)",
                "priority": 9
            },
            {
                "id": "google/gemma-3-27b-it",
                "display_name": "Gemma 3 27B Instruct",
                "context_length": 131072,
                "notes": "Fast, efficient, excellent instruction following (Google)",
                "priority": 8
            },
            {
                "id": "mistralai/mistral-large-latest",
                "display_name": "Mistral Large 3",
                "context_length": 256000,
                "notes": "Top open-weight multimodal, agentic & tool strong (Mistral AI, French)",
                "priority": 9
            },
            {
                "id": "ibm/granite-4.0-8b-instruct",
                "display_name": "Granite 4.0 8B Instruct",
                "context_length": 128000,
                "notes": "Enterprise-tuned, improved tool calling & reasoning (IBM, American)",
                "priority": 7
            },
            {
                "id": "openai/gpt-oss-120b",
                "display_name": "GPT-OSS 120B",
                "context_length": 128000,
                "notes": "Open-weight OpenAI model, solid tool use & reasoning",
                "priority": 8
            },
            {
                "id": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
                "display_name": "Nemotron Super 49B",
                "context_length": 131072,
                "notes": "Tool-augmented specialist, strong RAG/agent (NVIDIA, American)",
                "priority": 7
            },
        ],
        "image": [
            {
                "id": "google/gemini-3.1-pro-preview",
                "display_name": "Gemini 3.1 Pro Preview",
                "context_length": 1000000,
                "notes": "Excellent vision + reasoning, 1M context (Google)",
                "priority": 9
            },
            {
                "id": "mistralai/pixtral-large-latest",
                "display_name": "Pixtral Large",
                "context_length": 128000,
                "notes": "Multimodal flagship, strong image understanding (Mistral)",
                "priority": 8
            },
        ]
    },

    "together": {
        "text": [
            {
                "id": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "display_name": "Llama 3.3 70B Turbo",
                "context_length": 128000,
                "notes": "Fast quantized version, great tool calling (Meta)",
                "priority": 9
            },
            {
                "id": "mistralai/Mistral-7B-Instruct-v0.3",
                "display_name": "Mistral 7B Instruct v0.3",
                "context_length": 32768,
                "notes": "Speed demon, reliable function calling (Mistral)",
                "priority": 8
            },
            {
                "id": "ibm/granite-3.1-8b-instruct",
                "display_name": "Granite 3.1 8B Instruct",
                "context_length": 128000,
                "notes": "Enterprise reasoning & tool tuned (IBM)",
                "priority": 7
            },
        ],
        "image": []
    },

    "ollama": {
        "text": [
            {
                "id": "llama3.3:70b-instruct",
                "display_name": "Llama 3.3 70B Instruct (local)",
                "context_length": 128000,
                "notes": "Top local generalist, good agents/tools",
                "priority": 9
            },
            {
                "id": "mistral:7b-instruct-v0.3",
                "display_name": "Mistral 7B Instruct v0.3 (local)",
                "context_length": 32768,
                "notes": "Fast local inference, solid function calling",
                "priority": 8
            },
            {
                "id": "granite3.2:8b",
                "display_name": "Granite 3.2 8B (local)",
                "context_length": 128000,
                "notes": "IBM enterprise-tuned, tool improvements",
                "priority": 7
            },
            {
                "id": "gemma2:27b-instruct",
                "display_name": "Gemma 2 27B Instruct (local)",
                "context_length": 8192,
                "notes": "Efficient Google model, strong instruction",
                "priority": 7
            },
        ],
        "image": [
            {
                "id": "llava",
                "display_name": "LLaVA (vision local)",
                "context_length": 4096,
                "notes": "Classic local multimodal",
                "priority": 8
            },
        ]
    },

    "mistral": {
        "text": [
            {
                "id": "mistral-large-latest",
                "display_name": "Mistral Large 3",
                "context_length": 256000,
                "notes": "Flagship, excellent agentic/tool use",
                "priority": 10
            },
            {
                "id": "devstral-latest",
                "display_name": "Devstral 2",
                "context_length": 128000,
                "notes": "Coding/agent specialist",
                "priority": 9
            },
        ],
        "image": [
            {
                "id": "pixtral-large-latest",
                "display_name": "Pixtral Large",
                "context_length": 128000,
                "notes": "Strong vision + text",
                "priority": 9
            },
        ]
    },

    "openai": {
        "text": [
            {
                "id": "gpt-4o",
                "display_name": "GPT-4o",
                "context_length": 128000,
                "notes": "Mature tool calling, reliable baseline",
                "priority": 9
            },
            {
                "id": "gpt-oss-120b",
                "display_name": "GPT-OSS 120B",
                "context_length": 128000,
                "notes": "Open-weight OpenAI, good agents",
                "priority": 8
            },
        ],
        "image": [
            {
                "id": "gpt-4o",
                "display_name": "GPT-4o (vision)",
                "context_length": 128000,
                "notes": "Built-in multimodal",
                "priority": 9
            },
        ]
    }
}
