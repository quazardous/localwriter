"""Auto-generated module manifest. DO NOT EDIT."""

VERSION = '1.1.1'

MODULES = [
    {
        "name": "main",
        "description": "LocalWriter global settings",
        "requires": [],
        "provides_services": [],
        "config": {
                "debug": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Debug Mode"
                }
        },
        "actions": [
                "about"
        ],
        "action_icons": {}
},
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
        },
        "actions": [],
        "action_icons": {}
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
        },
        "actions": [],
        "action_icons": {}
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
        },
        "actions": [],
        "action_icons": {}
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
        },
        "actions": [],
        "action_icons": {}
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
        "config": {},
        "actions": [],
        "action_icons": {}
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
        },
        "actions": [],
        "action_icons": {}
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
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "http",
        "description": "HTTP server for extension endpoints",
        "requires": [
                "config",
                "events"
        ],
        "provides_services": [
                "http_routes"
        ],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Enable HTTP Server",
                        "public": True
                },
                "port": {
                        "type": "int",
                        "default": 8766,
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
                        "helper": "Optional. Leave empty to use auto-generated self-signed certificate.",
                        "file_filter": "PEM files (*.pem)|*.pem|All files (*.*)|*.*"
                },
                "ssl_key": {
                        "type": "string",
                        "default": "",
                        "widget": "file",
                        "label": "SSL Private Key",
                        "helper": "Optional. Leave empty to use auto-generated self-signed key.",
                        "file_filter": "PEM files (*.pem)|*.pem"
                }
        },
        "actions": [
                "toggle_server",
                "server_status"
        ],
        "action_icons": {
                "toggle_server": "running",
                "server_status": "stopped"
        }
},
    {
        "name": "mcp",
        "description": "MCP JSON-RPC server for external tool access",
        "requires": [
                "document",
                "config",
                "events",
                "http_routes"
        ],
        "provides_services": [],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Enable MCP Protocol",
                        "public": True
                }
        },
        "actions": [],
        "action_icons": {}
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
        },
        "actions": [
                "extend_selection",
                "edit_selection"
        ],
        "action_icons": {}
},
    {
        "name": "tunnel",
        "description": "Tunnel providers for exposing MCP externally",
        "requires": [
                "config",
                "events",
                "http_routes"
        ],
        "provides_services": [
                "tunnel_manager"
        ],
        "config": {
                "auto_start": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Auto Start Tunnel",
                        "public": True
                },
                "provider": {
                        "type": "string",
                        "default": "",
                        "widget": "select",
                        "label": "Tunnel Provider",
                        "options_provider": "plugin.modules.tunnel:get_provider_options"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "batch",
        "description": "Batch tool execution with variable chaining",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "writer.nav",
        "description": "Writer document navigation \u2014 bookmarks, heading tree, proximity",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [
                "writer_bookmarks",
                "writer_tree",
                "writer_proximity"
        ],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "writer.index",
        "description": "Full-text search with stemming for Writer documents",
        "requires": [
                "document",
                "config",
                "events",
                "writer_tree"
        ],
        "provides_services": [
                "writer_index"
        ],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.bore",
        "description": "Bore tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {
                "server": {
                        "type": "string",
                        "default": "bore.pub",
                        "widget": "text",
                        "label": "Bore Server",
                        "helper": "The bore server address (default: bore.pub)"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.cloudflare",
        "description": "Cloudflare tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {
                "tunnel_name": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Tunnel Name"
                },
                "public_url": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Public URL",
                        "helper": "The public URL assigned by Cloudflare"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.ngrok",
        "description": "Ngrok tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {
                "authtoken": {
                        "type": "string",
                        "default": "",
                        "widget": "password",
                        "label": "Auth Token",
                        "helper": "Your ngrok authentication token"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.tailscale",
        "description": "Tailscale Funnel tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "common",
        "description": "Common tools for all document types",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
]
