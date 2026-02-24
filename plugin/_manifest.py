"""Auto-generated module manifest. DO NOT EDIT."""

VERSION = '1.0.0'

MODULES = [
    {
        "name": "core",
        "description": "Core services (document, config, events, llm, image, format)",
        "requires": [],
        "provides_services": [
                "document",
                "config",
                "events",
                "llm",
                "image",
                "format"
        ],
        "config": {
                "log_level": {
                        "type": "string",
                        "default": "WARN",
                        "widget": "select",
                        "label": "Log Level",
                        "public": True,
                        "options": [
                                {
                                        "value": "DEBUG",
                                        "label": "Debug"
                                },
                                {
                                        "value": "INFO",
                                        "label": "Info"
                                },
                                {
                                        "value": "WARN",
                                        "label": "Warning"
                                },
                                {
                                        "value": "ERROR",
                                        "label": "Error"
                                }
                        ]
                }
        }
},
    {
        "name": "calc",
        "description": "Calc spreadsheet tools (cells, sheets, formulas, charts)",
        "requires": [
                "document",
                "config"
        ],
        "provides_services": [],
        "config": {
                "max_rows_display": {
                        "type": "int",
                        "default": 1000,
                        "min": 100,
                        "max": 100000,
                        "widget": "number",
                        "label": "Max Rows Display",
                        "public": True
                }
        }
},
    {
        "name": "openai_compat",
        "description": "OpenAI-compatible API backend (OpenAI, OpenRouter, LM Studio, etc.)",
        "requires": [
                "config",
                "events"
        ],
        "provides_services": [
                "llm"
        ],
        "config": {
                "endpoint": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "API Endpoint",
                        "placeholder": "https://api.openai.com/v1",
                        "public": True
                },
                "api_key": {
                        "type": "string",
                        "default": "",
                        "widget": "password",
                        "label": "API Key"
                },
                "model": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Model",
                        "placeholder": "gpt-4o-mini",
                        "public": True
                },
                "temperature": {
                        "type": "float",
                        "default": 0.7,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "widget": "slider",
                        "label": "Temperature"
                },
                "max_tokens": {
                        "type": "int",
                        "default": 4096,
                        "min": 1,
                        "max": 128000,
                        "widget": "number",
                        "label": "Max Tokens"
                },
                "request_timeout": {
                        "type": "int",
                        "default": 120,
                        "min": 10,
                        "max": 600,
                        "widget": "number",
                        "label": "Request Timeout (seconds)"
                }
        }
},
    {
        "name": "chatbot",
        "description": "AI chat sidebar",
        "requires": [
                "document",
                "config",
                "events",
                "llm"
        ],
        "provides_services": [],
        "config": {
                "max_tool_rounds": {
                        "type": "int",
                        "default": 15,
                        "min": 1,
                        "max": 50,
                        "widget": "number",
                        "label": "Max Tool Rounds"
                },
                "system_prompt": {
                        "type": "string",
                        "default": "",
                        "widget": "textarea",
                        "label": "System Prompt"
                },
                "image_provider": {
                        "type": "string",
                        "default": "endpoint",
                        "widget": "select",
                        "label": "Image Provider",
                        "options": [
                                {
                                        "value": "endpoint",
                                        "label": "LLM Endpoint"
                                },
                                {
                                        "value": "horde",
                                        "label": "AI Horde (free)"
                                }
                        ]
                },
                "show_mcp_activity": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Show MCP Activity",
                        "public": True
                }
        }
},
    {
        "name": "horde",
        "description": "AI Horde image generation (free, no key required)",
        "requires": [
                "config",
                "events"
        ],
        "provides_services": [
                "image"
        ],
        "config": {
                "api_key": {
                        "type": "string",
                        "default": "0000000000",
                        "widget": "text",
                        "label": "API Key (optional)",
                        "description": "Leave default for anonymous access",
                        "public": True
                },
                "model": {
                        "type": "string",
                        "default": "stable_diffusion",
                        "widget": "select",
                        "label": "Model",
                        "public": True,
                        "options": [
                                {
                                        "value": "stable_diffusion",
                                        "label": "Stable Diffusion"
                                },
                                {
                                        "value": "stable_diffusion_xl",
                                        "label": "SDXL"
                                }
                        ]
                },
                "max_wait": {
                        "type": "int",
                        "default": 5,
                        "min": 1,
                        "max": 30,
                        "widget": "number",
                        "label": "Max Wait (minutes)"
                },
                "nsfw": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Allow NSFW"
                }
        }
},
    {
        "name": "draw",
        "description": "Draw/Impress tools (shapes, pages/slides)",
        "requires": [
                "document",
                "config",
                "image"
        ],
        "provides_services": [],
        "config": {}
},
    {
        "name": "mcp",
        "description": "MCP JSON-RPC server for external tool access",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Enable MCP Server",
                        "public": True
                },
                "port": {
                        "type": "int",
                        "default": 8765,
                        "min": 1024,
                        "max": 65535,
                        "widget": "number",
                        "label": "Server Port",
                        "public": True
                },
                "host": {
                        "type": "string",
                        "default": "localhost",
                        "widget": "text",
                        "label": "Bind Address",
                        "public": True
                },
                "use_ssl": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Enable HTTPS",
                        "public": True
                },
                "ssl_cert": {
                        "type": "string",
                        "default": "",
                        "widget": "file",
                        "label": "SSL Certificate",
                        "file_filter": "PEM files (*.pem)|*.pem|All files (*.*)|*.*"
                },
                "ssl_key": {
                        "type": "string",
                        "default": "",
                        "widget": "file",
                        "label": "SSL Private Key",
                        "file_filter": "PEM files (*.pem)|*.pem"
                }
        }
},
    {
        "name": "ollama",
        "description": "Ollama local LLM backend",
        "requires": [
                "config",
                "events"
        ],
        "provides_services": [
                "llm"
        ],
        "config": {
                "endpoint": {
                        "type": "string",
                        "default": "http://localhost:11434",
                        "widget": "text",
                        "label": "Ollama URL",
                        "public": True
                },
                "model": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Model",
                        "placeholder": "llama3.2",
                        "public": True
                },
                "temperature": {
                        "type": "float",
                        "default": 0.7,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "widget": "slider",
                        "label": "Temperature"
                },
                "max_tokens": {
                        "type": "int",
                        "default": 4096,
                        "min": 1,
                        "max": 128000,
                        "widget": "number",
                        "label": "Max Tokens"
                },
                "request_timeout": {
                        "type": "int",
                        "default": 300,
                        "min": 10,
                        "max": 600,
                        "widget": "number",
                        "label": "Request Timeout (seconds)",
                        "description": "Ollama may need longer for initial model loading"
                }
        }
},
    {
        "name": "writer",
        "description": "Writer document tools (outline, content, comments, styles, tables, tracking, images)",
        "requires": [
                "document",
                "config",
                "format",
                "image"
        ],
        "provides_services": [],
        "config": {
                "max_content_chars": {
                        "type": "int",
                        "default": 50000,
                        "min": 1000,
                        "max": 500000,
                        "widget": "number",
                        "label": "Max Content Size",
                        "public": True
                }
        }
},
]
