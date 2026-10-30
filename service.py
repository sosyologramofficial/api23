"""
Service Module - Self-Contained MyEdit Online Integration
Integrates with myEditOnline services.
Uses temp-mail.asia temp mail for on-the-fly account registration and verification.
Saves created accounts directly to the database.
"""
import os
import json
import time
import random
import secrets
import string
import struct
import re
import base64
import threading
import atexit
import ssl
import urllib.parse
import urllib.request
from urllib.parse import quote
import requests
from typing import Union
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import database as db

# Graceful shutdown event
_shutdown_event = threading.Event()
atexit.register(lambda: _shutdown_event.set())




# ==============================================================================
# MYEDIT API ENDPOINT'LERI VE SABITLER
# ==============================================================================
INIT_URL = "https://cse.cyberlink.com/cse/v2/init"
MEMBER_INIT_URL = "https://mauth.cyberlink.com/member-auth/v1/init"
SIGNUP_URL = "https://mauth.cyberlink.com/member-auth/public/sign-up"
LOGIN_URL = "https://mauth.cyberlink.com/member-auth/public/sign-in"
TOKEN_EXCHANGE_URL = "https://cse.cyberlink.com/cse/v2/getCseTokenByMember"
DAILY_BONUS_URL = "https://credit.cyberlink.com/v1/member/daily-bonus/get"
CREDIT_KEY_URL = "https://credit.cyberlink.com/v1/app/key"
CREDIT_TASK_BONUS_GET_URL = "https://credit.cyberlink.com/v1/app/task-bonus/get"
CREDIT_MEMBER_REMAIN_URL = "https://credit.cyberlink.com/v2/member/remain"
SUB_AUTH_URL = "https://myedit.online/api/cloud/subscriptions/auth"

MYEDIT_TTI_URL = "https://myedit.online/tti/effect"
MYEDIT_VGEN_URL = "https://myedit.online/vgen/effect"
MYEDIT_VGEN_BUSY_URL = "https://myedit.online/vgen/effect/busy"

AES_IV = b"CyberLinkCSE"  # CSE modulu icin 12 byte sabit IV
CREDIT_IV = b"CyberLinkCredit"  # Credit modulu icin 16 byte IV ve AAD
SID_AOL_POL = "ae44600d"  # MyEdit Service ID

MYEDIT_HARDCODED_RSA_PUB = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtvujIyahk6iftVcwDe/N2IN6f6YDebIE/"
    "y9HlOe78HjywtLB4f39MkBJyQItum8IaoPn+cS2JHTDG9oGgSuE47kLqVQH51rZ7Aw+L19Sv8B+8p7CsDDt"
    "OM2QjR7ypa/cAugt0ao0t9eH+vMkiMhsYkZ6uvUDgod+KskwjyDTaGXlAlSc8Orztn44xsGSCxUz86lgsuzRE0"
    "VHPYdVHYYMV8xT3qhExvtNobu2z2wxRUM4TLN397CkANGQLScnQlbG92MMVsFoSBrycSCjv6zUlBFMmnVR4l5"
    "m5CHGbe/2/iNXjhf1aA7XpJVZ/2HybuDUUDSjnsTNDqXU/p2++GT8WQIDAQAB"
)

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://myedit.online",
    "Referer": "https://myedit.online/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
}

MEMBER_AUTH_PUB_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtUnkrBbgQQLnHdk8d7LsDtC/rkQa9rTe7"
    "ZHwqf7jT1fqMGKFqa/4ESplrcyd6xmqt5m65v+IXBxhNFaqPZOrfMTxD5Kg1ZhlecfytcLR2Tuzg6"
    "MXVnDBzTJgU46rIRyzuippauieeoQZGNghxfDeOOveihZBYNwIYl3zK4DXZckm/Ils5wn3ZFEdJja"
    "ZEV4JFj6vOMDlORmRoCCZZ1xYvIbjSbXdRM9XsPuOK99ucwS750xycVB4qkAzrUvfJLiBw4rQgA7s"
    "g44/iMAlt2X71yLP6zYVVzuHQDcvQiWDJfymZfooPPehRf0cW+amWW4qmNsfhQVvY7AVijCBuC3QMw"
    "IDAQAB"
)
MEMBER_AUTH_IV = b"CLMemberAuth"
MEMBER_AUTH_KEY_ID = 2

MEMBER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://mauth.cyberlink.com",
    "Referer": "https://mauth.cyberlink.com/auth/myedit/signup?mode=myedit&isBusiness=false&lang=ENU",
    "User-Agent": HEADERS["User-Agent"],
}


# ==============================================================================
# RESIM MODEL CONFIGURATIONS
# ==============================================================================
IMAGE_MODELS_CONFIG = {
    # ==========================================================================
    # FEATURED (ANA LISTE)
    # ==========================================================================
    "gpt_image_2_5_sunburst": {
        "name": "GPT Image 2.5 Sunburst",
        "vendor": "OpenAI",
        "actionId_prefix": "genimage_1_img_openai_gptimage2.5sunburst",
        "promptLength": 32000,
        "ref_img_limit": 16,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 6},
            "enable": {"1K": 3, "2K": 6},
        },
        "default_style": "Style_1003_Custom_ChatGPT",
        "process_time": 90,
    },
    "gpt_image_2_5_flare": {
        "name": "GPT-Image-2.5 Flare",
        "vendor": "OpenAI",
        "actionId_prefix": "genimage_1_img_openai_gptimage2.5flare",
        "promptLength": 32000,
        "ref_img_limit": 16,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 6},
            "enable": {"1K": 3, "2K": 6},
        },
        "default_style": "Style_1004_Custom_ChatGPT",
        "process_time": 90,
    },
    "gpt_image_2": {
        "name": "GPT-Image-2",
        "vendor": "OpenAI",
        "actionId_prefix": "genimage_1_img_openai_gptimage2",
        "promptLength": 8000,
        "ref_img_limit": 16,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 6},
            "enable": {"1K": 3, "2K": 6},
        },
        "default_style": "Style_1002_Custom_ChatGPT",
        "process_time": 90,
    },
    "gemini_3_pro": {
        "name": "Gemini 3 Pro (Nano Banana Pro)",
        "vendor": "Google",
        "actionId_prefix": "genimage_1_img_google_gemini3pro",
        "promptLength": 2500,
        "ref_img_limit": 14,
        "supported_resolutions": ["1K", "2K", "4K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 6, "2K": 6, "4K": 12},
            "enable": {"1K": 6, "2K": 6, "4K": 12},
        },
        "default_style": "Style_3001_Custom_Gemini",
        "process_time": 60,
    },
    "gemini_3_1_flash": {
        "name": "Gemini 3.1 Flash (Nano Banana 2)",
        "vendor": "Google",
        "actionId_prefix": "genimage_1_img_google_gemini3.1flash",
        "promptLength": 2500,
        "ref_img_limit": 14,
        "supported_resolutions": ["1K", "2K", "4K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 5, "4K": 7},
            "enable": {"1K": 3, "2K": 5, "4K": 7},
        },
        "default_style": "Style_3002_Custom_Gemini",
        "process_time": 60,
    },
    "gemini_nanobanana_2_1": {
        "name": "Gemini Nano Banana 2.1",
        "vendor": "Google",
        "actionId_prefix": "genimage_1_img_google_gemininanobanana2.1",
        "promptLength": 2500,
        "ref_img_limit": 14,
        "supported_resolutions": ["1K", "2K", "4K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 4, "4K": 8},
            "enable": {"1K": 3, "2K": 4, "4K": 8},
        },
        "default_style": "Style_3004_Custom_Gemini",
        "process_time": 60,
    },
    "seedream_5_pro": {
        "name": "SeeDream 5.0 Pro",
        "vendor": "ByteDance",
        "actionId_prefix": "genimage_1_img_bytedance_seedream5.0pro",
        "promptLength": 600,
        "ref_img_limit": 10,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 5},
            "enable": {"1K": 3, "2K": 5},
        },
        "default_style": "Style_9001_Custom_Seedream",
        "process_time": 120,
    },
    "flux_2_pro": {
        "name": "Flux 2 Pro",
        "vendor": "BlackForest",
        "actionId_prefix": "genimage_1_img_blackforest_flux2pro",
        "promptLength": 2500,
        "ref_img_limit": 4,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 2, "2K": 5},
            "enable": {"1K": 3, "2K": 6},
        },
        "default_style": "Style_7000_Custom_FluxAPI",
        "process_time": 40,
    },
    "qwen_image_3_pro": {
        "name": "Qwen Image 3.0 Pro",
        "vendor": "Alibaba",
        "actionId_prefix": "genimage_1_img_alibaba_qwenimage3.0pro",
        "promptLength": 4500,
        "ref_img_limit": 3,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 5},
            "enable": {"1K": 3, "2K": 5},
        },
        "default_style": "Style_001_Custom_QwenAPI",
        "process_time": 100,
    },
    "qwen_image_3": {
        "name": "Qwen Image 3.0",
        "vendor": "Alibaba",
        "actionId_prefix": "genimage_1_img_alibaba_qwenimage3.0",
        "promptLength": 4500,
        "ref_img_limit": 3,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 2, "2K": 3},
            "enable": {"1K": 2, "2K": 3},
        },
        "default_style": "Style_000_Custom_QwenAPI",
        "process_time": 100,
    },

    # ==========================================================================
    # MORE MODELS (ALT LISTE)
    # ==========================================================================
    "gemini_3_1_flash_lite": {
        "name": "Gemini 3.1 Flash Lite (Nano Banana 2 Lite)",
        "vendor": "Google",
        "actionId_prefix": "genimage_1_img_google_gemini3.1flashlite",
        "promptLength": 2500,
        "ref_img_limit": 14,
        "supported_resolutions": ["1K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 2},
            "enable": {"1K": 2},
        },
        "default_style": "Style_3003_Custom_Gemini",
        "process_time": 60,
    },
    "gemini_2_5_flash": {
        "name": "Gemini 2.5 Flash (Nano Banana)",
        "vendor": "Google",
        "actionId_prefix": "genimage_1_img_google_gemini2.5flash",
        "promptLength": 2500,
        "ref_img_limit": 3,
        "supported_resolutions": ["1K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 2},
            "enable": {"1K": 2},
        },
        "default_style": "Style_3000_Custom_Gemini",
        "process_time": 30,
    },
    "seedream_5_lite": {
        "name": "SeeDream 5.0 Lite",
        "vendor": "ByteDance",
        "actionId_prefix": "genimage_1_img_bytedance_seedream5.0lite",
        "promptLength": 600,
        "ref_img_limit": 14,
        "supported_resolutions": ["2K", "3K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"2K": 3, "3K": 3},
            "enable": {"2K": 3, "3K": 3},
        },
        "default_style": "Style_9000_Custom_Seedream",
        "process_time": 60,
    },
    "gpt_image_1_5": {
        "name": "GPT-Image-1.5",
        "vendor": "OpenAI",
        "actionId_prefix": "genimage_1_img_openai_gptimage1.5",
        "promptLength": 2500,
        "ref_img_limit": 16,
        "supported_resolutions": ["1K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3},
            "enable": {"1K": 3},
        },
        "default_style": "Style_1001_Custom_ChatGPT",
        "process_time": 30,
    },
    "gpt_image_1": {
        "name": "GPT-Image-1",
        "vendor": "OpenAI",
        "actionId_prefix": "genimage_1_img_openai_gptimage1",
        "promptLength": 2500,
        "ref_img_limit": 16,
        "supported_resolutions": ["1K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 2},
            "enable": {"1K": 2},
        },
        "default_style": "Style_1000_Custom_ChatGPT",
        "process_time": 30,
    },
    "z_image": {
        "name": "Z-Image",
        "vendor": "CyberLink",
        "actionId_prefix": "genimage_1_img_cyberlink_zimageturbo",
        "promptLength": 800,
        "ref_img_limit": 0,
        "supported_resolutions": ["1K", "2K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 1, "2K": 2},
        },
        "default_style": "Style_000_Custom_ZImage",
        "process_time": 15,
    },
    "kling_o3": {
        "name": "Kling O3",
        "vendor": "Kling",
        "actionId_prefix": "genimage_1_img_kling_o3",
        "promptLength": 2500,
        "ref_img_limit": 10,
        "supported_resolutions": ["1K", "2K", "4K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 3, "4K": 5},
            "enable": {"1K": 3, "2K": 3, "4K": 5},
        },
        "default_style": "Style_5001_Custom_Kling",
        "process_time": 60,
    },
    "kling_o1": {
        "name": "Kling O1",
        "vendor": "Kling",
        "actionId_prefix": "genimage_1_img_kling_o1",
        "promptLength": 2500,
        "ref_img_limit": 10,
        "supported_resolutions": ["1K", "2K", "4K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 3, "2K": 3, "4K": 5},
            "enable": {"1K": 3, "2K": 3, "4K": 5},
        },
        "default_style": "Style_5000_Custom_Kling",
        "process_time": 40,
    },
    "flux_dev": {
        "name": "Flux Dev 1",
        "vendor": "CyberLink",
        "actionId_prefix": "genimage_1_img_cyberlink_fluxdev1",
        "promptLength": 800,
        "ref_img_limit": 0,
        "supported_resolutions": ["1K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 1},
        },
        "default_style": "Style_047_None_Flux",
        "process_time": 20,
    },
    "stable_diffusion": {
        "name": "Stable Diffusion XL",
        "vendor": "CyberLink",
        "actionId_prefix": "genimage_1_img_cyberlink_stablediffusion",
        "promptLength": 800,
        "ref_img_limit": 1,
        "supported_resolutions": ["1K"],
        "supported_aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "credits": {
            "none": {"1K": 1},
            "enable": {"1K": 1},
        },
        "default_style": "Style_Default",
        "effect_type": "TtiStyleRef",
        "process_time": 15,
    },
}


# Image Model ID Mapping (Frontend / API ID -> Backend Model ID)
IMAGE_MODEL_MAPPING = {
    "NANO_BANANA": "gemini_2_5_flash",
    "NANO_BANANA_2": "gemini_3_1_flash",
    "NANO_BANANA_PRO": "gemini_3_pro",
    "GPT_IMAGE_2": "gpt_image_2",
    # Fallback / case-insensitive aliases
    "gemini_2_5_flash": "gemini_2_5_flash",
    "gemini_3_1_flash": "gemini_3_1_flash",
    "gemini_3_pro": "gemini_3_pro",
    "gpt_image_2": "gpt_image_2",
    "nano_banana": "gemini_2_5_flash",
    "nano_banana_2": "gemini_3_1_flash",
    "nano_banana_pro": "gemini_3_pro",
}

# Direct mapping in IMAGE_MODELS_CONFIG for safety
IMAGE_MODELS_CONFIG["NANO_BANANA"] = IMAGE_MODELS_CONFIG["gemini_2_5_flash"]
IMAGE_MODELS_CONFIG["NANO_BANANA_2"] = IMAGE_MODELS_CONFIG["gemini_3_1_flash"]
IMAGE_MODELS_CONFIG["NANO_BANANA_PRO"] = IMAGE_MODELS_CONFIG["gemini_3_pro"]
IMAGE_MODELS_CONFIG["GPT_IMAGE_2"] = IMAGE_MODELS_CONFIG["gpt_image_2"]

VIDEO_MODELS_CONFIG = {
    # ==========================================================================
    # SEEDANCE (BytePlus)
    # ==========================================================================
    "seedance_2_0_fast": {
        "name": "Seedance 2.0 Fast",
        "model": "dreamina-seedance-2-0-fast-260128",
        "vendor": "BytePlus",
        "promptLength": 20000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["480p", "720p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(4, 16)),
        "duration_config": {'type': 'continuous', 'min': 4, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p"],
            "TextToVideo": ["480p", "720p"],
            "ReferenceToVideo": ["480p", "720p"],
        },
        "action_id": "genvideo_1_sec_bytedance_seedance2.0fast_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_bytedance_custom_seedance2.0fast_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("none", "480p"): 3,
            ("none", "720p"): 6,
            ("vendor", "480p"): 3,
            ("vendor", "720p"): 6,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 9,
            "max_videos": 3,
            "max_total": 12,
            "max_video_duration": 15,
        },
    },
    "seedance_2_0_mini": {
        "name": "Seedance 2.0 Mini",
        "model": "dreamina-seedance-2-0-mini-260615",
        "vendor": "BytePlus",
        "promptLength": 20000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["480p", "720p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(4, 16)),
        "duration_config": {'type': 'continuous', 'min': 4, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p"],
            "TextToVideo": ["480p", "720p"],
            "ReferenceToVideo": ["480p", "720p"],
        },
        "action_id": "genvideo_1_sec_bytedance_seedance2.0mini_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_bytedance_custom_seedance2.0mini_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("none", "480p"): 2,
            ("none", "720p"): 4,
            ("vendor", "480p"): 2,
            ("vendor", "720p"): 4,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 9,
            "max_videos": 3,
            "max_total": 12,
            "max_video_duration": 15,
        },
    },
    "seedance_2_0_pro": {
        "name": "Seedance 2.0 Pro",
        "model": "dreamina-seedance-2-0-260128",
        "vendor": "BytePlus",
        "promptLength": 20000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["480p", "720p", "1080p", "4K"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(4, 16)),
        "duration_config": {'type': 'continuous', 'min': 4, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["480p", "720p", "1080p", "4K"],
            "ReferenceToVideo": ["480p", "720p", "1080p", "4K"],
        },
        "action_id": "genvideo_1_sec_bytedance_seedance2.0std_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_bytedance_custom_seedance2.0std_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("none", "480p"): 4,
            ("none", "720p"): 8,
            ("none", "1080p"): 18,
            ("none", "4K"): 32,
            ("vendor", "480p"): 4,
            ("vendor", "720p"): 8,
            ("vendor", "1080p"): 18,
            ("vendor", "4K"): 32,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 9,
            "max_videos": 3,
            "max_total": 12,
            "max_video_duration": 15,
        },
    },
    "seedance_2_5": {
        "name": "Seedance 2.5",
        "model": "dreamina-seedance-2-5-260628",
        "vendor": "BytePlus",
        "promptLength": 20000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["480p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(4, 31)),
        "duration_config": {'type': 'continuous', 'min': 4, 'max': 30, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["480p", "720p", "1080p"],
            "TextToVideo": ["480p", "720p", "1080p"],
            "ReferenceToVideo": ["480p", "720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_bytedance_seedance2.5std_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_bytedance_custom_seedance2.5std_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("none", "480p"): 6,
            ("none", "720p"): 12,
            ("none", "1080p"): 24,
            ("vendor", "480p"): 6,
            ("vendor", "720p"): 12,
            ("vendor", "1080p"): 24,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 20,
            "max_videos": 10,
            "max_total": 20,
            "max_video_duration": 30,
        },
    },

    # ==========================================================================
    # ALIBABA (Wan & Happy Horse)
    # ==========================================================================
    "happy_horse_1_1": {
        "name": "Happy Horse 1.1",
        "model": {
            "TextToVideo": "happyhorse-1.1-t2v",
            "ImageToVideo": "happyhorse-1.1-i2v",
            "ReferenceToVideo": "happyhorse-1.1-r2v",
        },
        "vendor": "Alibaba",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1"],
        "supported_durations": list(range(3, 16)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["720p", "1080p"],
            "ReferenceToVideo": ["720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_alibaba_happyhorse1.1_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_alibaba_custom_happyhorse1.1_{sound}_{frame_mode}_1080p",
        "credit_map": {
            ("none", "720p"): 5,
            ("none", "1080p"): 8,
            ("vendor", "720p"): 5,
            ("vendor", "1080p"): 8,
        },
        "reference_media_limit": {
            "supported_types": ["image"],
            "max_images": 9,
            "max_media": 9,
        },
    },
    "happy_horse_1_0": {
        "name": "Happy Horse 1.0",
        "model": {
            "TextToVideo": "happyhorse-1.0-t2v",
            "ImageToVideo": "happyhorse-1.0-i2v",
            "ReferenceToVideo": "happyhorse-1.0-r2v",
        },
        "vendor": "Alibaba",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1"],
        "supported_durations": list(range(3, 16)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["720p", "1080p"],
            "ReferenceToVideo": ["720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_alibaba_happyhorse1.0_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_alibaba_custom_happyhorse1.0_{sound}_{frame_mode}_1080p",
        "credit_map": {
            ("none", "720p"): 5,
            ("none", "1080p"): 8,
            ("vendor", "720p"): 5,
            ("vendor", "1080p"): 8,
        },
        "reference_media_limit": {
            "supported_types": ["image"],
            "max_images": 9,
            "max_media": 9,
        },
    },
    "wan_2_7": {
        "name": "Wan 2.7",
        "model": {
            "TextToVideo": "wan2.7-t2v",
            "ImageToVideo": "wan2.7-i2v",
            "ReferenceToVideo": "wan2.7-r2v",
        },
        "vendor": "Alibaba",
        "promptLength": 5000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1"],
        "supported_durations": list(range(2, 16)),
        "duration_config": {'type': 'continuous', 'min': 2, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["720p", "1080p"],
            "ReferenceToVideo": ["720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_alibaba_wan2.7_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_alibaba_custom_wan2.7_{sound}_{frame_mode}_1080p",
        "credit_map": {
            ("none", "720p"): 5,
            ("none", "1080p"): 8,
            ("vendor", "720p"): 5,
            ("vendor", "1080p"): 8,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 5,
            "max_videos": 5,
            "max_total": 5,
            "max_video_duration": 30,
        },
    },
    "wan_3_0": {
        "name": "Wan 3.0",
        "model": "wan3.0-video",
        "vendor": "Alibaba",
        "promptLength": 19000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["480p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(2, 31)),
        "duration_config": {'type': 'continuous', 'min': 2, 'max': 30, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["480p", "720p", "1080p"],
            "ReferenceToVideo": ["480p", "720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_alibaba_wan3.0_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_alibaba_custom_wan3.0_{sound}_{frame_mode}_1080p",
        "credit_map": {
            ("none", "480p"): 2,
            ("none", "720p"): 4,
            ("none", "1080p"): 8,
            ("vendor", "480p"): 2,
            ("vendor", "720p"): 4,
            ("vendor", "1080p"): 8,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 10,
            "max_videos": 5,
            "max_total": 15,
            "max_video_duration": 15,
        },
    },

    # ==========================================================================
    # GOOGLE (Veo & Gemini Omni)
    # ==========================================================================
    "veo_3_1": {
        "name": "Veo 3.1",
        "model": "veo-3.1-generate-preview",
        "vendor": "Google",
        "promptLength": 4000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p", "4k"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": [4, 6, 8],
        "duration_config": {'type': 'discrete', 'options': [4, 6, 8], 'default': 4},
        "action_id": "genvideo_1_sec_google_veo3.1std_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_google_custom_veo3.1std_{sound}_{frame_mode}",
        "credit_map": {
            ("TextToVideo", "none", "720p"): 10,
            ("TextToVideo", "none", "1080p"): 10,
            ("TextToVideo", "none", "4k"): 20,
            ("TextToVideo", "vendor", "720p"): 18,
            ("TextToVideo", "vendor", "1080p"): 18,
            ("TextToVideo", "vendor", "4k"): 30,
            ("ImageToVideo", "none", "single", "720p"): 10,
            ("ImageToVideo", "none", "single", "1080p"): 10,
            ("ImageToVideo", "none", "single", "4k"): 10,
            ("ImageToVideo", "none", "startend", "720p"): 10,
            ("ImageToVideo", "none", "startend", "1080p"): 10,
            ("ImageToVideo", "none", "startend", "4k"): 10,
            ("ImageToVideo", "vendor", "single", "720p"): 18,
            ("ImageToVideo", "vendor", "single", "1080p"): 18,
            ("ImageToVideo", "vendor", "single", "4k"): 18,
            ("ImageToVideo", "vendor", "startend", "720p"): 18,
            ("ImageToVideo", "vendor", "startend", "1080p"): 18,
            ("ImageToVideo", "vendor", "startend", "4k"): 18,
        },
    },
    "veo_3_1_fast": {
        "name": "Veo 3.1 Fast",
        "model": "veo-3.1-fast-generate-preview",
        "vendor": "Google",
        "promptLength": 4000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p", "4k"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": [4, 6, 8],
        "duration_config": {'type': 'discrete', 'options': [4, 6, 8], 'default': 4},
        "action_id": "genvideo_1_sec_google_veo3.1fast_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_google_custom_veo3.1fast_{sound}_{frame_mode}",
        "credit_map": {
            ("TextToVideo", "none", "720p"): 5,
            ("TextToVideo", "none", "1080p"): 7,
            ("TextToVideo", "none", "4k"): 14,
            ("TextToVideo", "vendor", "720p"): 7,
            ("TextToVideo", "vendor", "1080p"): 9,
            ("TextToVideo", "vendor", "4k"): 16,
            ("ImageToVideo", "none", "single", "720p"): 5,
            ("ImageToVideo", "none", "single", "1080p"): 5,
            ("ImageToVideo", "none", "single", "4k"): 5,
            ("ImageToVideo", "none", "startend", "720p"): 5,
            ("ImageToVideo", "none", "startend", "1080p"): 5,
            ("ImageToVideo", "none", "startend", "4k"): 5,
            ("ImageToVideo", "vendor", "single", "720p"): 8,
            ("ImageToVideo", "vendor", "single", "1080p"): 8,
            ("ImageToVideo", "vendor", "single", "4k"): 8,
            ("ImageToVideo", "vendor", "startend", "720p"): 8,
            ("ImageToVideo", "vendor", "startend", "1080p"): 8,
            ("ImageToVideo", "vendor", "startend", "4k"): 8,
        },
    },
    "veo_3_1_lite": {
        "name": "Veo 3.1 Lite",
        "model": "veo-3.1-lite-generate-001",
        "vendor": "Google",
        "promptLength": 4000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": [4, 6, 8],
        "duration_config": {'type': 'discrete', 'options': [4, 6, 8], 'default': 4},
        "action_id": "genvideo_1_sec_google_veo3.1lite_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_google_custom_veo3.1lite_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("none", "720p"): 2,
            ("none", "1080p"): 3,
            ("vendor", "720p"): 3,
            ("vendor", "1080p"): 5,
        },
    },
    "gemini_omni_flash": {
        "name": "Gemini Omni 1.1 Flash",
        "model": "gemini-omni-1.1-flash-preview",
        "vendor": "Google",
        "promptLength": 3500,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["360p", "720p", "1080p", "4k"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": list(range(3, 11)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 10, 'step': 1, 'default': 5},
        "action_id": "genvideo_1_sec_google_geminiomni1.1flash_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_google_custom_geminiomni1.1flash_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("TextToVideo", "none", "360p"): 2,
            ("TextToVideo", "none", "720p"): 5,
            ("TextToVideo", "none", "1080p"): 8,
            ("TextToVideo", "none", "4k"): 8,
            ("TextToVideo", "vendor", "360p"): 2,
            ("TextToVideo", "vendor", "720p"): 5,
            ("TextToVideo", "vendor", "1080p"): 8,
            ("TextToVideo", "vendor", "4k"): 8,
            ("ImageToVideo", "none", "360p"): 2,
            ("ImageToVideo", "none", "720p"): 5,
            ("ImageToVideo", "none", "1080p"): 8,
            ("ImageToVideo", "none", "4k"): 15,
            ("ImageToVideo", "vendor", "360p"): 2,
            ("ImageToVideo", "vendor", "720p"): 5,
            ("ImageToVideo", "vendor", "1080p"): 8,
            ("ImageToVideo", "vendor", "4k"): 15,
            ("ReferenceToVideo", "none", "360p"): 2,
            ("ReferenceToVideo", "none", "720p"): 5,
            ("ReferenceToVideo", "none", "1080p"): 8,
            ("ReferenceToVideo", "none", "4k"): 15,
            ("ReferenceToVideo", "vendor", "360p"): 2,
            ("ReferenceToVideo", "vendor", "720p"): 5,
            ("ReferenceToVideo", "vendor", "1080p"): 8,
            ("ReferenceToVideo", "vendor", "4k"): 15,
        },
        "reference_media_limit": {
            "supported_types": ["image"],
            "max_images": 5,
            "max_media": 5,
        },
    },

    # ==========================================================================
    # KLING (Kuaishou)
    # ==========================================================================
        "kling_4_0": {
        "name": "Kling 4.0",
        "model": "kling-4.0",
        "vendor": "Kling",
        "mode": "pro",
        "promptLength": 11000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(3, 31)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 30, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p", "1080p"],
            "TextToVideo": ["720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_kling_4.0std_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_kling_custom_4.0std_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("TextToVideo", "none", "720p"): 9,
            ("TextToVideo", "enable", "720p"): 11,
            ("TextToVideo", "vendor", "720p"): 11,
            ("TextToVideo", "none", "1080p"): 14,
            ("TextToVideo", "enable", "1080p"): 16,
            ("TextToVideo", "vendor", "1080p"): 16,
            ("ImageToVideo", "none", "single", "720p"): 9,
            ("ImageToVideo", "enable", "single", "720p"): 9,
            ("ImageToVideo", "vendor", "single", "720p"): 9,
            ("ImageToVideo", "none", "startend", "720p"): 9,
            ("ImageToVideo", "enable", "startend", "720p"): 9,
            ("ImageToVideo", "vendor", "startend", "720p"): 9,
            ("ImageToVideo", "none", "single", "1080p"): 14,
            ("ImageToVideo", "enable", "single", "1080p"): 14,
            ("ImageToVideo", "vendor", "single", "1080p"): 14,
            ("ImageToVideo", "none", "startend", "1080p"): 14,
            ("ImageToVideo", "enable", "startend", "1080p"): 14,
            ("ImageToVideo", "vendor", "startend", "1080p"): 14,
            ("none", "720p"): 9,
            ("vendor", "720p"): 11,
            ("enable", "720p"): 11,
            ("none", "1080p"): 14,
            ("vendor", "1080p"): 16,
            ("enable", "1080p"): 16,
        },
    },
"kling_3_0": {
        "name": "Kling 3.0",
        "model": "kling-v3",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p", "4k"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(3, 16)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p", "1080p"],
            "TextToVideo": ["720p", "1080p", "4k"],
        },
        "action_id": "genvideo_1_sec_kling_3.0pro_{sound}_1080p",
        "action_id_overrides": {
            "720p": "genvideo_1_sec_kling_3.0std_{sound}_720p",
            "1080p": "genvideo_1_sec_kling_3.0pro_{sound}_1080p",
            "4k": "genvideo_1_sec_kling_3.04k_{sound}_4k",
        },
        "action_id_i2v": "genvideo_1_sec_kling_custom_3.0pro_{sound}_{frame_mode}_1080p",
        "action_id_i2v_overrides": {
            "720p": "genvideo_1_sec_kling_custom_3.0std_{sound}_{frame_mode}_720p",
            "1080p": "genvideo_1_sec_kling_custom_3.0pro_{sound}_{frame_mode}_1080p",
        },
        "credit_map": {
            ("none", "720p"): 4,
            ("none", "1080p"): 5,
            ("none", "4k"): 14,
            ("vendor", "720p"): 6,
            ("vendor", "1080p"): 8,
            ("vendor", "4k"): 14,
        },
    },
    "kling_o3": {
        "name": "Kling O3",
        "model": "kling-v3-omni",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p", "4k"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(3, 16)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p", "1080p"],
            "TextToVideo": ["720p", "1080p", "4k"],
            "ReferenceToVideo": ["720p", "1080p", "4k"],
        },
        "action_id": "genvideo_1_sec_kling_o3pro_{sound}_1080p",
        "action_id_overrides": {
            "720p": "genvideo_1_sec_kling_o3std_{sound}_720p",
            "1080p": "genvideo_1_sec_kling_o3pro_{sound}_1080p",
            "4k": "genvideo_1_sec_kling_o34k_{sound}_4k",
        },
        "action_id_i2v": "genvideo_1_sec_kling_custom_o3pro_{sound}_{frame_mode}_1080p",
        "action_id_i2v_overrides": {
            "720p": "genvideo_1_sec_kling_custom_o3std_{sound}_{frame_mode}_720p",
            "1080p": "genvideo_1_sec_kling_custom_o3pro_{sound}_{frame_mode}_1080p",
        },
        "credit_map": {
            ("none", "720p"): 4,
            ("none", "1080p"): 5,
            ("none", "4k"): 14,
            ("vendor", "720p"): 5,
            ("vendor", "1080p"): 6,
            ("vendor", "4k"): 14,
        },
        "reference_media_limit": {
            "supported_types": ["image"],
            "max_images": 7,
            "max_media": 7,
        },
    },
    "kling_2_6": {
        "name": "Kling 2.6",
        "model": "kling-v2-6",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": [5, 10],
        "duration_config": {'type': 'discrete', 'options': [5, 10], 'default': 5},
        "action_id": "genvideo_1_sec_kling_2.6pro_{sound}_1080p",
        "action_id_i2v": "genvideo_1_sec_kling_custom_2.6pro_{sound}_{frame_mode}",
        "credit_map": {
            ("ImageToVideo", "none", "1080p"): 5,
            ("ImageToVideo", "vendor", "1080p"): 8,
            ("TextToVideo", "none", "1080p"): 4,
            ("TextToVideo", "vendor", "1080p"): 8,
        },
    },
    "kling_2_5_pro": {
        "name": "Kling 2.5 Pro",
        "model": "kling-v2-5-turbo",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": [5, 10],
        "duration_config": {'type': 'discrete', 'options': [5, 10], 'default': 5},
        "action_id": "genvideo_1_sec_kling_2.5pro_{sound}_1080p",
        "action_id_i2v": "genvideo_1_sec_kling_custom_2.5pro_{sound}_{frame_mode}",
        "credit_map": {
            ("ImageToVideo", "none", "1080p"): 5,
            ("ImageToVideo", "vendor", "1080p"): 5,
            ("TextToVideo", "none", "1080p"): 4,
            ("TextToVideo", "vendor", "1080p"): 4,
        },
    },
    "kling_2_5_std": {
        "name": "Kling 2.5 Standard",
        "model": "kling-v2-5-turbo",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["720p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": [5, 10],
        "duration_config": {'type': 'discrete', 'options': [5, 10], 'default': 5},
        "action_id": "genvideo_1_sec_kling_2.5std_{sound}_720p",
        "action_id_i2v": "genvideo_1_sec_kling_custom_2.5std_{sound}_single",
        "credit_map": {
            ("ImageToVideo", "none", "720p"): 3,
            ("ImageToVideo", "vendor", "720p"): 3,
            ("TextToVideo", "none", "720p"): 2,
            ("TextToVideo", "vendor", "720p"): 2,
        },
    },
    "kling_o1_pro": {
        "name": "Kling O1 Pro",
        "model": "kling-video-o1",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": [5, 10],
        "duration_config": {'type': 'discrete', 'options': [5, 10], 'default': 5},
        "action_id_i2v": "genvideo_1_sec_kling_custom_o1pro_{sound}_{frame_mode}",
        "credit_map": {
            ("none", "1080p"): 6,
            ("vendor", "1080p"): 6,
        },
    },
    "kling_o1_std": {
        "name": "Kling O1 Standard",
        "model": "kling-video-o1",
        "vendor": "Kling",
        "promptLength": 2500,
        "supported_modes": ["ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": [5, 10],
        "duration_config": {'type': 'discrete', 'options': [5, 10], 'default': 5},
        "action_id_i2v": "genvideo_1_sec_kling_custom_o1std_{sound}_{frame_mode}",
        "credit_map": {
            ("none", "720p"): 4,
            ("vendor", "720p"): 4,
        },
    },

    # ==========================================================================
    # VIDU (ShengShu)
    # ==========================================================================
        "vidu_q4": {
        "name": "Vidu Q4",
        "model": "viduq4",
        "vendor": "Vidu",
        "promptLength": 5000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(3, 17)),
        "duration_config": {'type': 'continuous', 'min': 3, 'max': 16, 'step': 1, 'default': 5},
        "action_id": "genvideo_1_sec_vidu_custom_q4_{sound}_single_1080p",
        "action_id_i2v": "genvideo_1_sec_vidu_custom_q4_{sound}_single_1080p",
        "credit_map": {
            ("none", "1080p"): 6,
            ("vendor", "1080p"): 6,
            ("enable", "1080p"): 6,
        },
    },
"vidu_q3_pro": {
        "name": "Vidu Q3 Pro",
        "model": "viduq3-pro",
        "vendor": "Vidu",
        "promptLength": 2000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["540p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(1, 17)),
        "duration_config": {'type': 'continuous', 'min': 1, 'max': 16, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["540p", "720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_vidu_q3pro_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_vidu_custom_q3pro_{sound}_{frame_mode}_1080p",
        "credit_map": {
            ("none", "540p"): 3,
            ("none", "720p"): 5,
            ("none", "1080p"): 6,
            ("vendor", "540p"): 3,
            ("vendor", "720p"): 5,
            ("vendor", "1080p"): 6,
        },
    },
    "vidu_q3_turbo": {
        "name": "Vidu Q3 Turbo",
        "model": "viduq3-turbo",
        "vendor": "Vidu",
        "promptLength": 2000,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["540p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(1, 17)),
        "duration_config": {'type': 'continuous', 'min': 1, 'max': 16, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p"],
            "TextToVideo": ["540p", "720p", "1080p"],
            "ReferenceToVideo": ["540p", "720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_vidu_q3turbo_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_vidu_custom_q3turbo_{sound}_{frame_mode}_720p",
        "credit_map": {
            ("none", "540p"): 2,
            ("none", "720p"): 3,
            ("none", "1080p"): 4,
            ("vendor", "540p"): 2,
            ("vendor", "720p"): 3,
            ("vendor", "1080p"): 4,
        },
        "reference_media_limit": {
            "supported_types": ["image"],
            "max_images": 7,
            "max_media": 7,
        },
    },
    "vidu_q2_pro": {
        "name": "Vidu Q2 Pro",
        "model": {
            "TextToVideo": "viduq2",
            "ImageToVideo": "viduq2-pro",
        },
        "vendor": "Vidu",
        "promptLength": 2000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["540p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(1, 11)),
        "duration_config": {'type': 'continuous', 'min': 1, 'max': 10, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["1080p"],
            "TextToVideo": ["540p", "720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_vidu_q2_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_vidu_custom_q2pro_{sound}_{frame_mode}",
        "credit_map": {
            ("ImageToVideo", "none", "1080p"): 3,
            ("ImageToVideo", "vendor", "1080p"): 3,
            ("TextToVideo", "none", "540p"): 1,
            ("TextToVideo", "none", "720p"): 2,
            ("TextToVideo", "none", "1080p"): 3,
            ("TextToVideo", "vendor", "540p"): 1,
            ("TextToVideo", "vendor", "720p"): 2,
            ("TextToVideo", "vendor", "1080p"): 3,
        },
    },
    "vidu_q2_turbo": {
        "name": "Vidu Q2 Turbo",
        "model": {
            "TextToVideo": "viduq2",
            "ImageToVideo": "viduq2-turbo",
        },
        "vendor": "Vidu",
        "promptLength": 2000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["540p", "720p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(1, 11)),
        "duration_config": {'type': 'continuous', 'min': 1, 'max': 10, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["540p", "720p"],
            "TextToVideo": ["540p", "720p"],
        },
        "action_id": "genvideo_1_sec_vidu_q2_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_vidu_custom_q2turbo_{sound}_{frame_mode}",
        "credit_map": {
            ("ImageToVideo", "none", "540p"): 3,
            ("ImageToVideo", "none", "720p"): 3,
            ("ImageToVideo", "vendor", "540p"): 3,
            ("ImageToVideo", "vendor", "720p"): 3,
            ("TextToVideo", "none", "540p"): 1,
            ("TextToVideo", "none", "720p"): 2,
            ("TextToVideo", "vendor", "540p"): 1,
            ("TextToVideo", "vendor", "720p"): 2,
        },
    },
    "vidu_q2": {
        "name": "Vidu Q2",
        "model": {
            "TextToVideo": "viduq2",
            "ImageToVideo": "viduq2-turbo",
        },
        "vendor": "Vidu",
        "promptLength": 2000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["540p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(1, 11)),
        "duration_config": {'type': 'continuous', 'min': 1, 'max': 10, 'step': 1, 'default': 5},
        "action_id": "genvideo_1_sec_vidu_q2_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_vidu_custom_q2turbo_{sound}_{frame_mode}",
        "action_id_i2v_overrides": {
            "1080p": "genvideo_1_sec_vidu_custom_q2pro_{sound}_{frame_mode}",
            "720p": "genvideo_1_sec_vidu_custom_q2turbo_{sound}_{frame_mode}",
            "540p": "genvideo_1_sec_vidu_custom_q2turbo_{sound}_{frame_mode}",
        },
        "credit_map": {
            ("ImageToVideo", "none", "540p"): 3,
            ("ImageToVideo", "none", "720p"): 3,
            ("ImageToVideo", "none", "1080p"): 3,
            ("ImageToVideo", "vendor", "540p"): 3,
            ("ImageToVideo", "vendor", "720p"): 3,
            ("ImageToVideo", "vendor", "1080p"): 3,
            ("TextToVideo", "none", "540p"): 1,
            ("TextToVideo", "none", "720p"): 2,
            ("TextToVideo", "none", "1080p"): 3,
            ("TextToVideo", "vendor", "540p"): 1,
            ("TextToVideo", "vendor", "720p"): 2,
            ("TextToVideo", "vendor", "1080p"): 3,
        },
    },

    # ==========================================================================
    # PIXVERSE
    # ==========================================================================
    "pixverse_v6": {
        "name": "PixVerse V6",
        "model": "v6",
        "vendor": "Pixverse",
        "promptLength": 4900,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["540p", "720p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(1, 16)),
        "duration_config": {'type': 'continuous', 'min': 1, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p", "1080p"],
            "TextToVideo": ["540p", "720p", "1080p"],
            "ReferenceToVideo": ["540p", "720p", "1080p"],
        },
        "action_id": "genvideo_1_sec_motivai_pixverse6_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_motivai_custom_pixverse6_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("TextToVideo", "none", "540p"): 1,
            ("TextToVideo", "none", "720p"): 2,
            ("TextToVideo", "none", "1080p"): 4,
            ("TextToVideo", "vendor", "540p"): 2,
            ("TextToVideo", "vendor", "720p"): 3,
            ("TextToVideo", "vendor", "1080p"): 6,
            ("ReferenceToVideo", "none", "540p"): 1,
            ("ReferenceToVideo", "none", "720p"): 2,
            ("ReferenceToVideo", "none", "1080p"): 4,
            ("ReferenceToVideo", "vendor", "540p"): 2,
            ("ReferenceToVideo", "vendor", "720p"): 3,
            ("ReferenceToVideo", "vendor", "1080p"): 6,
            ("ImageToVideo", "none", "single", "720p"): 2,
            ("ImageToVideo", "none", "startend", "720p"): 3,
            ("ImageToVideo", "none", "single", "1080p"): 4,
            ("ImageToVideo", "none", "startend", "1080p"): 6,
            ("ImageToVideo", "vendor", "single", "720p"): 2,
            ("ImageToVideo", "vendor", "startend", "720p"): 3,
            ("ImageToVideo", "vendor", "single", "1080p"): 4,
            ("ImageToVideo", "vendor", "startend", "1080p"): 6,
        },
        "reference_media_limit": {
            "supported_types": ["image"],
            "max_images": 7,
            "max_media": 7,
        },
    },

    # ==========================================================================
    # OPENAI (Sora)
    # ==========================================================================
    "sora_2_pro": {
        "name": "Sora 2 Pro",
        "model": "sora-2-pro",
        "vendor": "OpenAI",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["720p", "1024p", "1080p"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": [4, 8, 12],
        "duration_config": {'type': 'discrete', 'options': [4, 8, 12], 'default': 4},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["720p", "1080p"],
            "TextToVideo": ["720p", "1024p", "1080p"],
        },
        "action_id": "genvideo_1_sec_openai_sora2pro_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_openai_custom_sora2pro_{sound}_single",
        "credit_map": {
            ("TextToVideo", "none", "720p"): 16,
            ("TextToVideo", "none", "1024p"): 22,
            ("TextToVideo", "none", "1080p"): 28,
            ("TextToVideo", "vendor", "720p"): 16,
            ("TextToVideo", "vendor", "1024p"): 22,
            ("TextToVideo", "vendor", "1080p"): 28,
            ("ImageToVideo", "none", "single", "720p"): 18,
            ("ImageToVideo", "none", "single", "1080p"): 18,
            ("ImageToVideo", "vendor", "single", "720p"): 18,
            ("ImageToVideo", "vendor", "single", "1080p"): 18,
        },
    },
    "sora_2_std": {
        "name": "Sora 2 Standard",
        "model": "sora-2",
        "vendor": "OpenAI",
        "promptLength": 2500,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["720p"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": [4, 8, 12],
        "duration_config": {'type': 'discrete', 'options': [4, 8, 12], 'default': 4},
        "action_id": "genvideo_1_sec_openai_sora2_{sound}_720p",
        "action_id_i2v": "genvideo_1_sec_openai_custom_sora2std_{sound}_single",
        "credit_map": {
            ("none", "720p"): 6,
            ("vendor", "720p"): 6,
        },
    },

    # ==========================================================================
    # RUNWAY
    # ==========================================================================
    "runway_gen4_turbo": {
        "name": "Runway Gen4",
        "model": "gen4_turbo",
        "vendor": "Runway",
        "promptLength": 2500,
        "supported_modes": ["ImageToVideo"],
        "supported_frame_modes": ["single"],
        "supported_resolutions": ["720p"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supported_durations": [5, 10],
        "duration_config": {'type': 'discrete', 'options': [5, 10], 'default': 5},
        "action_id_i2v": "genvideo_1_sec_runway_custom_gen4turbo_{sound}_single",
        "credit_map": {
            ("none", "720p"): 3,
            ("vendor", "720p"): 3,
        },
    },
    # ==========================================================================
    # HAILUO (MiniMax)
    # ==========================================================================
    "minimax_h3": {
        "name": "MiniMax H3",
        "model": {
            "std": "MiniMax-H3",
            "max": "MiniMax-H3-Max",
        },
        "vendor": "Hailuo",
        "promptLength": 6900,
        "supported_modes": ["TextToVideo", "ImageToVideo", "ReferenceToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["480p", "768p", "2k"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(5, 16)),
        "duration_config": {'type': 'continuous', 'min': 5, 'max': 15, 'step': 1, 'default': 5},
        "supported_resolutions_by_mode": {
            "ImageToVideo": ["480p", "768p", "2k"],
            "TextToVideo": ["480p", "768p", "2k"],
            "ReferenceToVideo": ["480p", "768p", "2k"],
        },
        "action_id": "genvideo_1_sec_minimax_minimaxh3_{sound}_{resolution}",
        "action_id_overrides": {
            "480p": "genvideo_1_sec_minimax_minimaxh3max_{sound}_480p",
        },
        "action_id_i2v": "genvideo_1_sec_minimax_custom_minimaxh3_{sound}_{frame_mode}_{resolution}",
        "action_id_i2v_overrides": {
            "480p": "genvideo_1_sec_minimax_custom_minimaxh3max_{sound}_{frame_mode}_480p",
        },
        "credit_map": {
            ("none", "480p"): 3,
            ("vendor", "480p"): 3,
            ("enable", "480p"): 3,
            ("none", "768p"): 5,
            ("vendor", "768p"): 5,
            ("enable", "768p"): 5,
            ("none", "2k"): 8,
            ("vendor", "2k"): 8,
            ("enable", "2k"): 8,
        },
        "reference_media_limit": {
            "supported_types": ["image", "video"],
            "max_images": 9,
            "max_videos": 3,
            "max_total": 12,
            "max_video_duration": 15,
        },
    },

    # ==========================================================================
    # BLACKFOREST (Flux)
    # ==========================================================================
    "flux_3": {
        "name": "Flux 3",
        "model": "flux-3-video",
        "vendor": "Flux",
        "promptLength": 7000,
        "supported_modes": ["TextToVideo", "ImageToVideo"],
        "supported_frame_modes": ["single", "startend"],
        "supported_resolutions": ["720p", "1080p", "2k", "4k"],
        "supported_aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "supported_durations": list(range(5, 21)),
        "duration_config": {'type': 'continuous', 'min': 5, 'max': 20, 'step': 1, 'default': 5},
        "action_id": "genvideo_1_sec_blackforest_flux3_{sound}_{resolution}",
        "action_id_i2v": "genvideo_1_sec_blackforest_custom_flux3_{sound}_{frame_mode}_{resolution}",
        "credit_map": {
            ("none", "720p"): 9,
            ("vendor", "720p"): 9,
            ("enable", "720p"): 9,
            ("none", "1080p"): 15,
            ("vendor", "1080p"): 15,
            ("enable", "1080p"): 15,
            ("none", "2k"): 20,
            ("vendor", "2k"): 20,
            ("enable", "2k"): 20,
            ("none", "4k"): 35,
            ("vendor", "4k"): 35,
            ("enable", "4k"): 35,
        },
    },

}


# Video Model ID Mapping (Frontend / API ID -> Backend Model ID)
VIDEO_MODEL_MAPPING = {
    "VEO_3_1": "veo_3_1_lite",
    "GROK_VIDEO": "veo_3_1_lite",
    # Fallback / case-insensitive aliases
    "veo_3_1_lite": "veo_3_1_lite",
    "veo_3_1": "veo_3_1_lite",
    "grok_video": "veo_3_1_lite",
}

# Direct mapping in VIDEO_MODELS_CONFIG for safety
VIDEO_MODELS_CONFIG["VEO_3_1"] = VIDEO_MODELS_CONFIG["veo_3_1_lite"]
VIDEO_MODELS_CONFIG["GROK_VIDEO"] = VIDEO_MODELS_CONFIG["veo_3_1_lite"]


MODELS = {} # Compatibility mapping

AVAILABLE_MODELS = {
    "image": [
        {
            "id": "NANO_BANANA",
            "name": "Nano Banana",
            "description": "Nano Banana by Google - Supports up to 3 Reference Images",
            "supports_reference_images": True,
            "max_reference_images": 3,
            "supported_sizes": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            "supported_resolutions": ["1K"],
            "default_size": "1:1",
            "default_resolution": "1K",
            "max_prompt_length": 2500
        },
        {
            "id": "NANO_BANANA_2",
            "name": "Nano Banana 2",
            "description": "Nano Banana 2 by Google - Supports up to 14 Reference Images",
            "supports_reference_images": True,
            "max_reference_images": 5,
            "supported_sizes": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            "supported_resolutions": ["1K", "2K", "4K"],
            "default_size": "1:1",
            "default_resolution": "1K",
            "max_prompt_length": 2500
        },
        {
            "id": "NANO_BANANA_PRO",
            "name": "Nano Banana Pro",
            "description": "Nano Banana Pro by Google - Supports up to 14 Reference Images",
            "supports_reference_images": True,
            "max_reference_images": 5,
            "supported_sizes": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            "supported_resolutions": ["1K", "2K", "4K"],
            "default_size": "1:1",
            "default_resolution": "1K",
            "max_prompt_length": 2500
        },
        {
            "id": "GPT_IMAGE_2",
            "name": "GPT-Image-2",
            "description": "GPT-Image-2 by OpenAI - Supports up to 16 Reference Images",
            "supports_reference_images": True,
            "max_reference_images": 5,
            "supported_sizes": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            "supported_resolutions": ["1K", "2K"],
            "default_size": "1:1",
            "default_resolution": "1K",
            "max_prompt_length": 8000
        }
    ],
    "video": [
        {
            "id": "VEO_3_1",
            "name": "Veo 3.1",
            "description": "Veo 3.1 - Supports Start/End Frame",
            "supports_start_frame": True,
            "supports_end_frame": True,
            "supports_reference_images": False,
            "max_reference_images": 0,
            "supported_sizes": ["16:9", "9:16"],
            "supported_durations": [4, 6, 8],
            "supported_resolutions": ["720p", "1080p"],
            "default_size": "16:9",
            "default_resolution": "1080p",
            "default_duration": 4,
            "max_prompt_length": 4000
        },
        {
            "id": "GROK_VIDEO",
            "name": "Grok Video",
            "description": "Grok Video - Supports Start/End Frame",
            "supports_start_frame": True,
            "supports_end_frame": True,
            "supports_reference_images": False,
            "max_reference_images": 0,
            "supported_sizes": ["16:9", "9:16"],
            "supported_durations": [8],
            "supported_resolutions": ["720p"],
            "default_size": "16:9",
            "default_resolution": "720p",
            "default_duration": 8,
            "max_prompt_length": 4000
        }
    ],
    "tts": [],
    "music": []
}


def get_available_models(mode=None):
    import copy
    models = copy.deepcopy(AVAILABLE_MODELS)
    for model in models.get('video', []):
        actual_model_id = VIDEO_MODEL_MAPPING.get(model['id'], model['id'])
        config = VIDEO_MODELS_CONFIG.get(actual_model_id, {})
        if 'supported_modes' in config:
            model['supported_modes'] = config['supported_modes']
        if 'promptLength' in config:
            model['max_prompt_length'] = config['promptLength']
        if 'reference_media_limit' in config:
            model['reference_media_limit'] = config['reference_media_limit']
        if 'supported_frame_modes' in config:
            model['supported_frame_modes'] = config['supported_frame_modes']
        if config.get('supported_modes') == ['ImageToVideo']:
            model['requires_start_frame'] = True

        by_mode_res = config.get('supported_resolutions_by_mode')
        by_mode_dur = config.get('supported_durations_by_mode')
        if by_mode_res:
            model['supported_resolutions_by_mode'] = by_mode_res
        if by_mode_dur:
            model['supported_durations_by_mode'] = by_mode_dur
    if mode:
        return models.get(mode, [])
    return models

def make_proxy_url(raw_url):
    """
    Doğrudan ham medya URL'sini döner (proxy sarmalamasını devre dışı bırakır).
    """
    if not raw_url or not isinstance(raw_url, str):
        return raw_url
    if raw_url.startswith("/api/proxy?url="):
        import urllib.parse
        return urllib.parse.unquote(raw_url.split("/api/proxy?url=", 1)[1])
    return raw_url


from bs4 import BeautifulSoup

# ==============================================================================
# MYEDIT ONLINE ALTYAPI VE KRIPTOGRAFİK YARDIMCILAR (temp-mail.asia)
# ==============================================================================

# İSTEDİĞİN DOMAİNLERİ BURAYA GİREBİLİRSİN
# CyberLink ile stabil çalıştığı test edilen domainler listenin başındadır.
WHITELIST_DOMAINS = [
    # "umail.asia",
    # "cmail.asia",
    # "tempmailt.com",
    # "t-mail.asia",
    # "okyre.com",
    # "asia.banglatip.com",
    # "pmail.asia",
    # "1mail.edu.pl",
    "asia.1maill.com",
    "bd.1maill.com",
    "in.1maill.com",
    "bd.5secmail.com",
    "in.5secmail.com",
    "ng.5secmail.com",
    "asia.5secmail.com",
]

POLL_COMPONENTS = [
    "frontend.components.action",
    "frontend.components.token-login",
    "frontend.components.check-mail",
    "frontend.components.inbox-message",
]


def generate_random_username(length: int = 10) -> str:
    """Belirtilen uzunlukta harf ve rakamlardan oluşan rastgele bir kullanıcı adı üretir."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


# ==============================================================================
# TEMP MAIL PROXY AYARLARI (Render.com temp-mail.asia 403 Engeli İcin)
# ==============================================================================
# Render.com sunucularında temp-mail.asia IP engeline (403 Forbidden) takıldığı
# için sadece temp mail isteklerine özel bu proxy alanı tanımlanmıştır.
# Temp mail dışındaki CyberLink, resim, video vb. hiçbir istek bu proxy'yi KULLANMAZ.
#
# TEMP_MAIL_PROXY_MODE (Proxy Durumu):
#   1 -> Temp mail istekleri Webshare proxy üzerinden geçer (Render.com için 1 yapın).
#   0 -> Proxy devre dışı kalır, doğrudan sunucu IP'si üzerinden bağlanır.
TEMP_MAIL_PROXY_MODE = 1

TEMP_MAIL_PROXY_CONFIG = {
    "http": "http://nrrbciri-1:5cauzsujeluf@p.webshare.io:80",
    "https": "http://nrrbciri-1:5cauzsujeluf@p.webshare.io:80",
}


def apply_temp_mail_proxy(session: requests.Session):
    """Sadece TempMailClient oturumuna proxy uygular.
    
    İleride proxy'yi tamamen kaldırmak isterseniz bu bloğu ve TempMailClient
    içindeki apply_temp_mail_proxy(self.session) satırını silmeniz yeterlidir.
    """
    if TEMP_MAIL_PROXY_MODE == 1 and TEMP_MAIL_PROXY_CONFIG:
        session.proxies.update(TEMP_MAIL_PROXY_CONFIG)
# ==============================================================================


class TempMailClient:
    """temp-mail.asia Livewire Entegrasyonu"""

    BASE_URL = "https://temp-mail.asia"

    def __init__(self, domain: str = None):
        self.domain = domain
        self.box = None
        self.email = None
        self.session = requests.Session()
        apply_temp_mail_proxy(self.session)
        self.csrf = None
        self.components = {}
        self.lw_headers = {}
        self._seen_ids = set()

    def get_email(self, length: int = 10, domain: str = None) -> str:
        """Yeni bir geçici e-posta adresi üretir ve temp-mail.asia oturumuna bağlar."""
        if domain:
            self.domain = domain
        elif not self.domain and WHITELIST_DOMAINS:
            self.domain = WHITELIST_DOMAINS[0]

        init_headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/437.36"
            ),
            "upgrade-insecure-requests": "1",
        }

        resp = self.session.get(f"{self.BASE_URL}/", headers=init_headers, timeout=30)
        resp.raise_for_status()
        html = resp.text

        csrf_match = re.search(r'data-csrf=["\']([^"\']+)["\']', html)
        email_match = re.search(r"const email\s*=\s*'([^']+)'", html)
        self.csrf = csrf_match.group(1) if csrf_match else None
        default_email = email_match.group(1) if email_match else None

        soup = BeautifulSoup(html, "html.parser")
        self.components = {}
        for el in soup.find_all(attrs={"wire:snapshot": True}):
            raw_snap = el.get("wire:snapshot", "")
            try:
                snap_data = json.loads(raw_snap)
                name = snap_data.get("memo", {}).get("name", "")
                if name:
                    self.components[name] = {"snapshot": raw_snap, "name": name}
            except Exception:
                pass

        self.lw_headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
            "User-Agent": init_headers["User-Agent"],
            "x-livewire": "1",
            "x-csrf-token": self.csrf,
        }

        if self.domain:
            self.box = generate_random_username(length)
            target_email = f"{self.box}@{self.domain}"

            check_mail_comp = self.components.get("frontend.components.check-mail")
            if check_mail_comp and self.csrf:
                change_payload = {
                    "_token": self.csrf,
                    "components": [
                        {
                            "snapshot": check_mail_comp["snapshot"],
                            "updates": {
                                "username": self.box,
                                "domain": self.domain,
                            },
                            "calls": [
                                {
                                    "method": "checkEmailAddress",
                                    "params": [],
                                    "metadata": {},
                                }
                            ],
                        }
                    ],
                }
                try:
                    change_resp = self.session.post(
                        f"{self.BASE_URL}/livewire/update",
                        headers=self.lw_headers,
                        json=change_payload,
                        timeout=30,
                    )
                    if change_resp.ok:
                        for c in change_resp.json().get("components", []):
                            if c.get("snapshot"):
                                self.components["frontend.components.check-mail"]["snapshot"] = c["snapshot"]
                        self.email = target_email
                    else:
                        self.email = default_email or target_email
                except Exception as e:
                    print(f"[Temp Mail] checkEmailAddress uyarisi: {e}")
                    self.email = default_email or target_email
            else:
                self.email = default_email or target_email
        else:
            self.email = default_email

        print(f"[Temp Mail] Olusturuldu: {self.email}")
        return self.email

    def _build_poll_payload(self) -> dict:
        api_components = []
        for name in POLL_COMPONENTS:
            comp = self.components.get(name)
            if not comp:
                continue

            if name == "frontend.components.inbox-message":
                calls = [
                    {
                        "method": "__dispatch",
                        "params": ["syncEmail", {"email": self.email}],
                        "metadata": {},
                    },
                    {
                        "method": "__dispatch",
                        "params": ["fetchMessages", {}],
                        "metadata": {},
                    },
                ]
            else:
                calls = [
                    {
                        "method": "__dispatch",
                        "params": ["syncEmail", {"email": self.email}],
                        "metadata": {},
                    },
                ]
            api_components.append(
                {
                    "snapshot": comp["snapshot"],
                    "updates": {},
                    "calls": calls,
                }
            )
        return {"_token": self.csrf, "components": api_components}

    def _extract_activation_link(self, text: str) -> str:
        trace_links = re.findall(
            r'https?://membership\.cyberlink\.com/prog/event/autoedm/trace_mem\.jsp\?[^\s"\'<>]+',
            text,
        )
        for link in trace_links:
            link = link.replace("&amp;", "&").rstrip("\"'")
            if any(k in link for k in ["account-activate", "Activate", "active-member"]):
                return link

        general_links = re.findall(
            r'https?://[^\s"\'<>]*(?:cyberlink|myedit)[^\s"\'<>]*(?:activate|confirm|verify|token)[^\s"\'<>]*',
            text,
            re.IGNORECASE,
        )
        for link in general_links:
            link = link.replace("&amp;", "&").rstrip("\"'")
            if any(k in link for k in ["activate", "confirm", "verify"]):
                return link

        try:
            soup = BeautifulSoup(text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].replace("&amp;", "&").rstrip("\"'")
                if any(k in href for k in ["trace_mem", "activate", "confirm", "verify", "token"]) and any(
                    d in href for d in ["cyberlink", "myedit"]
                ):
                    return href
        except Exception:
            pass

        if trace_links:
            return trace_links[0].replace("&amp;", "&").rstrip("\"'")

        return None

    def _extract_code(self, text: str) -> str:
        codes = re.findall(r"\b\d{4,8}\b", text)
        return codes[0] if codes else None

    def _fetch_message_content(self, msg_id, inbox_snapshot) -> str:
        view_payload = {
            "_token": self.csrf,
            "components": [
                {
                    "snapshot": inbox_snapshot,
                    "updates": {},
                    "calls": [{"method": "updateView", "params": [msg_id], "metadata": {}}],
                }
            ],
        }
        view_resp = self.session.post(
            f"{self.BASE_URL}/livewire/update",
            headers=self.lw_headers,
            json=view_payload,
            timeout=30,
        )
        if not view_resp.ok:
            return ""

        all_text = []
        for comp_resp in view_resp.json().get("components", []):
            effects_html = comp_resp.get("effects", {}).get("html", "")
            if effects_html:
                all_text.append(effects_html)
            snap_str = comp_resp.get("snapshot", "")
            if snap_str:
                try:
                    snap = json.loads(snap_str)
                    msgs = snap.get("data", {}).get("messages", [])
                    if msgs and isinstance(msgs[0], list):
                        for group in msgs[0]:
                            if isinstance(group, list):
                                for m in group:
                                    if isinstance(m, dict) and "content" in m:
                                        all_text.append(m["content"])
                except Exception:
                    pass
        return "\n".join(all_text)

    def wait_for_activation_link(self, timeout: int = 60) -> str:
        print(f"[Temp Mail] Gelen kutusu sorgulaniyor ({self.email})...")
        deadline = time.time() + timeout
        inbox_snapshot = None

        while time.time() < deadline:
            inbox_keys = []
            try:
                payload = self._build_poll_payload()
                resp = self.session.post(
                    f"{self.BASE_URL}/livewire/update",
                    headers=self.lw_headers,
                    json=payload,
                    timeout=20,
                )
                if resp.ok:
                    data = resp.json()
                    resp_comps = data.get("components", [])
                    active_names = [n for n in POLL_COMPONENTS if n in self.components]

                    for i, rc in enumerate(resp_comps):
                        new_snap = rc.get("snapshot", "")
                        if not new_snap or i >= len(active_names):
                            continue
                        target_name = active_names[i]
                        self.components[target_name]["snapshot"] = new_snap

                        if target_name == "frontend.components.inbox-message":
                            try:
                                snap = json.loads(new_snap)
                                inbox_msgs = snap.get("data", {}).get("inbox_messages", [])
                                if isinstance(inbox_msgs, list):
                                    for item in inbox_msgs:
                                        if isinstance(item, dict) and "keys" in item:
                                            inbox_keys = item["keys"]
                                            inbox_snapshot = new_snap
                            except Exception:
                                pass
            except Exception as e:
                print(f"[Temp Mail] Poll uyarisi: {e}")

            unseen_keys = [k for k in inbox_keys if k not in self._seen_ids]
            if unseen_keys:
                for msg_id in unseen_keys:
                    self._seen_ids.add(msg_id)
                    print(f"[+] Yeni mail alindi! ID: {msg_id}")
                    content = self._fetch_message_content(msg_id, inbox_snapshot)
                    link = self._extract_activation_link(content)
                    if link:
                        print(f"  -> Aktivasyon linki bulundu: {link[:80]}...")
                        return link

            time.sleep(3)

        raise TimeoutError("Aktivasyon maili gelmedi!")

    def wait_for_code(self, timeout: int = 60) -> str:
        print(f"[Temp Mail] Kod bekleniyor ({self.email})...")
        deadline = time.time() + timeout
        inbox_snapshot = None

        while time.time() < deadline:
            inbox_keys = []
            try:
                payload = self._build_poll_payload()
                resp = self.session.post(
                    f"{self.BASE_URL}/livewire/update",
                    headers=self.lw_headers,
                    json=payload,
                    timeout=20,
                )
                if resp.ok:
                    data = resp.json()
                    resp_comps = data.get("components", [])
                    active_names = [n for n in POLL_COMPONENTS if n in self.components]

                    for i, rc in enumerate(resp_comps):
                        new_snap = rc.get("snapshot", "")
                        if not new_snap or i >= len(active_names):
                            continue
                        target_name = active_names[i]
                        self.components[target_name]["snapshot"] = new_snap

                        if target_name == "frontend.components.inbox-message":
                            try:
                                snap = json.loads(new_snap)
                                inbox_msgs = snap.get("data", {}).get("inbox_messages", [])
                                if isinstance(inbox_msgs, list):
                                    for item in inbox_msgs:
                                        if isinstance(item, dict) and "keys" in item:
                                            inbox_keys = item["keys"]
                                            inbox_snapshot = new_snap
                            except Exception:
                                pass
            except Exception as e:
                print(f"[Temp Mail] Poll uyarisi: {e}")

            unseen_keys = [k for k in inbox_keys if k not in self._seen_ids]
            if unseen_keys:
                for msg_id in unseen_keys:
                    self._seen_ids.add(msg_id)
                    print(f"[+] Yeni mail alindi! ID: {msg_id}")
                    content = self._fetch_message_content(msg_id, inbox_snapshot)
                    code = self._extract_code(content)
                    if code:
                        print(f"[+] Dogrulama kodu bulundu: {code}")
                        return code

            time.sleep(3)

        raise TimeoutError("Dogrulama kodu gelmedi!")

# ================= MemberAuth Enkripsyon =================

def get_member_auth_public_key():
    """Sunucudan MemberAuth RSA Acik Anahtarini ve Key ID (k)'yi dinamik olarak alir."""
    try:
        resp = requests.post(MEMBER_INIT_URL, json={"p": "myedit"}, headers=MEMBER_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("info", {})
        return data["public_key"], data["id"]
    except Exception as e:
        print(f"[!] MemberAuth init hatasi: {e}, statik anahtar kullaniliyor.")
        return MEMBER_AUTH_PUB_KEY, MEMBER_AUTH_KEY_ID

def create_member_auth_payload(user_data: dict):
    """MemberAuth API icin RSA-OAEP + AES-256-GCM sifreli payload uretir."""
    pub_key_b64, key_id = get_member_auth_public_key()
    der_bytes = base64.b64decode(pub_key_b64)
    public_key = serialization.load_der_public_key(der_bytes)

    # 1. Rastgele 256-bit AES-GCM Anahtari uret
    aes_key = AESGCM.generate_key(bit_length=256)

    # 2. AES anahtarini Sunucu RSA Acik Anahtari ile sifrele
    rsa_encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    a_param = base64.b64encode(rsa_encrypted_aes_key).decode("utf-8")

    # 3. Veriyi AES-GCM ile sifrele (IV = b"CLMemberAuth")
    json_bytes = json.dumps(user_data, separators=(",", ":")).encode("utf-8")
    aesgcm = AESGCM(aes_key)
    cipher_bytes = aesgcm.encrypt(MEMBER_AUTH_IV, json_bytes, None)
    data_param = base64.b64encode(cipher_bytes).decode("utf-8")

    return {
        "a": a_param,
        "data": data_param,
        "k": key_id,
    }, aes_key

def decrypt_member_auth_response(response_b64: str, aes_key: bytes):
    """MemberAuth API'den donen Base64 sifreli yaniti cozer."""
    enc_bytes = base64.b64decode(response_b64)
    aesgcm = AESGCM(aes_key)
    decrypted_bytes = aesgcm.decrypt(MEMBER_AUTH_IV, enc_bytes, None)
    return json.loads(decrypted_bytes.decode("utf-8"))

# ================= CSE Enkripsyon =================

def get_server_public_key():
    resp = requests.post(INIT_URL, json={"p": "myedit"}, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["public_key"], data["id"]

def create_payload(user_data: dict):
    pub_key_b64, key_id = get_server_public_key()
    der_bytes = base64.b64decode(pub_key_b64)
    public_key = serialization.load_der_public_key(der_bytes)
    aes_key = AESGCM.generate_key(bit_length=256)

    rsa_encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    a_param = base64.b64encode(rsa_encrypted_aes_key).decode("utf-8")

    json_bytes = json.dumps(user_data, separators=(",", ":")).encode("utf-8")
    aesgcm = AESGCM(aes_key)
    cipher_bytes = aesgcm.encrypt(AES_IV, json_bytes, None)
    data_param = base64.b64encode(cipher_bytes).decode("utf-8")

    return {
        "a": a_param,
        "data": data_param,
        "k": str(key_id),
    }, aes_key

def decrypt_response(response_b64: str, aes_key: bytes):
    enc_bytes = base64.b64decode(response_b64)
    aesgcm = AESGCM(aes_key)
    decrypted_bytes = aesgcm.decrypt(AES_IV, enc_bytes, None)
    return json.loads(decrypted_bytes.decode("utf-8"))

def signup(email: str, password: str, lang: str = "enu", country: str = "US"):
    """Kullanici kaydi olusturur (MemberAuth API)."""
    user_data = {
        "email": email,
        "password": password,
        "language": lang.upper(),
        "rec_upgrade": 0,
        "sid": "myedit",
        "nJoint": 62
    }
    payload, aes_key = create_member_auth_payload(user_data)
    res = requests.post(SIGNUP_URL, json=payload, headers=MEMBER_HEADERS, timeout=30)
    res.raise_for_status()
    body = res.json()
    if body.get("status") == "SUCCESS" and "info" in body:
        decrypted = decrypt_member_auth_response(body["info"], aes_key)
        return {"status": "SUCCESS", "info": decrypted}
    return body

def activate_account(activation_url: str):
    """Mail gelen aktivasyon linkini takip eder ve hesabi aktiflestirir."""
    print("Aktivasyon istegi gonderiliyor...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    resp = session.get(activation_url, allow_redirects=True, timeout=30)
    if resp.status_code == 200:
        print("[+] HESAP BASARIYLA AKTIFLESTIRILDI!")
        return True
    else:
        print("[-] Aktivasyon uyarisi: Beklenenden farkli bir sayfaya yonlendi.")
        return False

def login(email: str, password: str, lang: str = "enu", country: str = "US"):
    """Giris yapip cltoken ve memberToken alir (MemberAuth API)."""
    user_data = {
        "email": email,
        "password": password,
        "recaptcha": None,
        "sid": "myedit",
    }
    payload, aes_key = create_member_auth_payload(user_data)
    res = requests.post(LOGIN_URL, json=payload, headers=MEMBER_HEADERS, timeout=30)
    res.raise_for_status()
    body = res.json()
    if body.get("status") == "SUCCESS" and "info" in body:
        decrypted = decrypt_member_auth_response(body["info"], aes_key)
        return {"status": "SUCCESS", "info": decrypted}
    return body

def get_cse_token_by_member(member_token: str):
    """memberToken kullanarak cltoken (CSE Token) takasi yapar."""
    user_data = {"memberToken": member_token}
    payload, aes_key = create_payload(user_data)
    res = requests.post(TOKEN_EXCHANGE_URL, json=payload, headers=HEADERS, timeout=30)
    res.raise_for_status()
    body = res.json()
    if "response" in body:
        decrypted = decrypt_response(body["response"], aes_key)
        return decrypted
    return body

def get_daily_bonus(member_token: str):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {member_token}",
        "Origin": "https://myedit.online",
        "Referer": "https://myedit.online/",
        "User-Agent": HEADERS["User-Agent"],
    }
    payload = {"sid": SID_AOL_POL}
    res = requests.post(DAILY_BONUS_URL, json=payload, headers=headers, timeout=30)
    res.raise_for_status()
    return res.json()

def get_member_remaining_credits(member_token: str):
    try:
        url = f"{CREDIT_MEMBER_REMAIN_URL}?detail=true&lang=ENU&sid={SID_AOL_POL}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": HEADERS["User-Agent"],
            "Authorization": f"Bearer {member_token}",
            "Origin": "https://myedit.online",
            "Referer": "https://myedit.online/",
        }
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        credits_json = res.json()
        return credits_json
    except Exception:
        return None

def get_credit_server_public_key():
    resp = requests.get(CREDIT_KEY_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()["result"]
    return data["key"], data["id"]

def create_credit_payload(data_dict: dict):
    pub_key_b64, key_id = get_credit_server_public_key()
    der_bytes = base64.b64decode(pub_key_b64)
    public_key = serialization.load_der_public_key(der_bytes)
    aes_key = AESGCM.generate_key(bit_length=256)

    rsa_encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    a_param = base64.b64encode(rsa_encrypted_aes_key).decode("utf-8")

    json_bytes = json.dumps(data_dict, separators=(",", ":")).encode("utf-8")
    aesgcm = AESGCM(aes_key)
    cipher_bytes = aesgcm.encrypt(CREDIT_IV, json_bytes, CREDIT_IV)
    data_param = base64.b64encode(cipher_bytes).decode("utf-8")

    return {
        "a": a_param,
        "data": data_param,
        "id": str(key_id),
    }

def claim_task_bonus(member_token: str, feature_id: str = "TextToImage", claim_credit: int = None):
    try:
        data_obj = {
            "sid": SID_AOL_POL,
            "unique_id": "",
            "version": "temp_one_time_free",
            "event_id": feature_id,
            "member_token": member_token,
        }
        if claim_credit is not None:
            data_obj["claim_credit"] = claim_credit
        payload = create_credit_payload(data_obj)
        res = requests.post(CREDIT_TASK_BONUS_GET_URL, json=payload, headers=HEADERS, timeout=30)
        res.raise_for_status()
        return res.json()
    except Exception:
        return None

def check_task_bonus(member_token: str, feature_id: str = "TextToImage"):
    try:
        check_url = "https://credit.cyberlink.com/v1/app/task-bonus/check"
        data_obj = {
            "sid": SID_AOL_POL,
            "unique_id": "",
            "version": "temp_one_time_free",
            "event_id": feature_id,
            "member_token": member_token,
        }
        payload = create_credit_payload(data_obj)
        res = requests.post(check_url, json=payload, headers=HEADERS, timeout=30)
        res.raise_for_status()
        return res.json()
    except Exception:
        return None

def collect_all_bonuses(member_token: str):
    """Kullanicinin tum aktif task bonuslarini (kredilerini) ve gunluk bonusunu toplar (toplam 334 kredi)."""
    print("\n[Bonuses] Tum gunluk ve gorev bonuslari toplaniyor...")
    
    # 1. Gunluk Bonus (+3 Kredi)
    try:
        daily_res = get_daily_bonus(member_token)
        print(f"  -> Gunluk Bonus Toplama Sonucu: {daily_res.get('result', daily_res)}")
    except Exception as e:
        print(f"  [!] Gunluk bonus toplama hatasi: {e}")
        
    # 2. Aktif Gorev Bonuslari (Toplam 331 Kredi + 3 Gunluk = 334 Kredi)
    active_tasks = [
        "TextToImage",          # 14 Kredi
        "AICollage",            # 3 Kredi
        "AIReplacement",        # 6 Kredi
        "TextToVideo",          # 50 Kredi
        "ImageToVideo",         # 50 Kredi
        "Storytelling",         # 40 Kredi
        "LyricsToSong",         # 5 Kredi
        "VideoToVideo",         # 50 Kredi (Sohbetle Video Duzenleme)
        "AICinematicShorts",    # 40 Kredi (CineStory Sinematik Video)
        "VideoAutoReframe",     # 20 Kredi (Video Kadrajlama)
        "AITryOn_1",            # 6 Kredi (Kiyafet Deneme 1)
        "AITryOn_2",            # 6 Kredi (Evcil Hayvan Kiyafet)
        "AITryOn",              # 6 Kredi (Genel Kiyafet Deneme)
        "TrendingAITemplates",  # 6 Kredi (Trend AI Sablonlari)
        "AIHairstyleV2",        # 6 Kredi (AI Sac Modeli)
        "AIPhotoSlideshow",     # 6 Kredi (AI Foto Slayt Gosterisi)
        "AIHeadshotV2",         # 6 Kredi (AI Portre / Vesikalik)
        "AIMusicGeneratorV2",   # 11 Kredi (AI Muzik Uretici)
    ]
    
    for task_id in active_tasks:
        try:
            check_task_bonus(member_token, feature_id=task_id)
            claim_task_bonus(member_token, feature_id=task_id)
        except Exception as e:
            print(f"  [!] Gorev bonusu ({task_id}) toplanirken hata: {e}")
            
    # Toplam Kredi Durumunu Yazdir
    try:
        credits_json = get_member_remaining_credits(member_token)
        if credits_json:
            total_remain = credits_json.get("total_remain", 0)
            print(f"  -> Kalan Kredi Detayi: {total_remain} Kredi")
    except Exception:
        pass

def sync_feature_credit(feature_id: str = "TextToImage", action_id: str = "genimage_1_img_openai_gptimage2_none_1K", credit: int = 3):
    try:
        url = f"https://credit.cyberlink.com/v1/featurelist/feature?feature_id={feature_id}&action_id={action_id}&credit={credit}&min_unit=1&is_main=false&discount=0&sid={SID_AOL_POL}"
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        return True
    except Exception:
        return False

def build_myedit_iv(timestamp_ms: int, sid: int = 0) -> bytes:
    return struct.pack('>Q', timestamp_ms) + struct.pack('>I', sid)

def get_myedit_rsa_public_key():
    der_bytes = base64.b64decode(MYEDIT_HARDCODED_RSA_PUB)
    return serialization.load_der_public_key(der_bytes)

def rsa_encrypt_aes_key(public_key, aes_key: bytes) -> str:
    encrypted = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted).decode('utf-8')

def encrypt_myedit_aes_gcm(aes_key: bytes, plaintext: Union[str, bytes], timestamp_ms: int, sid: int = 0) -> str:
    iv = build_myedit_iv(timestamp_ms, sid)
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    aesgcm = AESGCM(aes_key)
    cipher_bytes = aesgcm.encrypt(iv, plaintext, None)
    return base64.b64encode(cipher_bytes).decode('utf-8')

def decrypt_myedit_aes_gcm(aes_key: bytes, ciphertext_b64: str, timestamp_ms: int, sid: int = 0) -> bytes:
    iv = build_myedit_iv(timestamp_ms, sid)
    enc_bytes = base64.b64decode(ciphertext_b64)
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(iv, enc_bytes, None)

def encrypt_myedit_aes_gcm_hex(aes_key: bytes, raw_bytes: bytes, timestamp_ms: int, sid: int = 0) -> str:
    iv = build_myedit_iv(timestamp_ms, sid)
    aesgcm = AESGCM(aes_key)
    cipher_bytes = aesgcm.encrypt(iv, raw_bytes, None)
    return cipher_bytes.hex()

def get_subscription_token(member_token: str) -> str:
    rsa_pub_key = get_myedit_rsa_public_key()
    aes_key = AESGCM.generate_key(bit_length=256)
    ts_ms = int(time.time() * 1000)

    key_param = rsa_encrypt_aes_key(rsa_pub_key, aes_key)
    cl_sid_json = json.dumps({"cl_sid": [SID_AOL_POL]}, separators=(',', ':'))
    receipt_param = encrypt_myedit_aes_gcm(aes_key, cl_sid_json, ts_ms, 0)

    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Authorization": f"Bearer {member_token}",
        "Content-Type": "application/json",
        "Origin": "https://myedit.online",
        "Referer": "https://myedit.online/",
    }
    body = {
        "product": "myedit",
        "version": "3.9.0",
        "versiontype": "3.9.0",
        "platform": "web",
        "receipt": receipt_param,
        "key": key_param,
        "timestamp": ts_ms,
    }
    resp = requests.post(SUB_AUTH_URL, json=body, headers=headers, timeout=30)
    if resp.status_code == 401:
        raise AuthExpiredError(f"Auth token expired on subscriptions/auth: {resp.text}")
    if resp.status_code == 403:
        raise CreditExhaustedError(f"Subscription auth forbidden/exhausted: {resp.text}")
    resp.raise_for_status()
    return resp.json()["subscription_token"]

def format_error_code(error) -> str:
    """Returns strictly the HTTP status code (e.g. '429', '500', '503', '504') for client/frontend log visibility."""
    if not error:
        return "500"
    if isinstance(error, requests.exceptions.RequestException):
        if hasattr(error, 'response') and error.response is not None:
            return str(error.response.status_code)
    
    err_str = str(error)
    match = re.search(r'\b(4\d{2}|5\d{2})\b', err_str)
    if match:
        return match.group(1)
    
    if "timeout" in err_str.lower():
        return "504"
    return "500"

def decrypt_downloaded_media(url: str, aes_key: bytes, enc_key_b64: str, enc_iv_b64: str, init_ts_ms: int, output_path: str = "output.bin"):
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        enc_bytes = resp.content
        raw_key = decrypt_myedit_aes_gcm(aes_key, enc_key_b64, init_ts_ms, 0)
        raw_iv = decrypt_myedit_aes_gcm(aes_key, enc_iv_b64, init_ts_ms, 0)
        aesgcm = AESGCM(raw_key)
        decrypted_bytes = aesgcm.decrypt(raw_iv, enc_bytes, None)
        with open(output_path, "wb") as f:
            f.write(decrypted_bytes)
        return os.path.abspath(output_path)
    except Exception:
        return None

# ==============================================================================
# VIDEO MODEL SPECIFIC FUNCTIONS
# ==============================================================================

def get_image_dimensions(file_path):
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            return img.width, img.height
    except ImportError:
        try:
            with open(file_path, 'rb') as f:
                head = f.read(24)
                if len(head) == 24 and head.startswith(b'\x89PNG\r\n\x1a\n'):
                    check = struct.unpack('>I', head[16:20])[0]
                    if check != 0x0d0a1a0a:
                        w, h = struct.unpack('>II', head[16:24])
                        return w, h
                elif head.startswith(b'\xff\xd8'):
                    f.seek(0)
                    size = 2
                    ftype = 0
                    while not 0xc0 <= ftype <= 0xcf or ftype in (0xc4, 0xc8, 0xcc):
                        f.seek(size, 1)
                        byte = f.read(1)
                        while ord(byte) == 0xff:
                            byte = f.read(1)
                        ftype = ord(byte)
                        size = struct.unpack('>H', f.read(2))[0] - 2
                    f.seek(1, 1)
                    h, w = struct.unpack('>HH', f.read(4))
                    return w, h
        except Exception:
            pass
        return 1280, 720

def check_vgen_busy(referer="https://myedit.online/en/video-editor/text-to-video/edit"):
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://myedit.online",
        "Referer": referer,
    }
    try:
        resp = requests.get(MYEDIT_VGEN_BUSY_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("busy", False)
    except Exception:
        return False

def prepare_image_for_vgen(image_path: str, aspect_ratio: str, target_w: int = None, target_h: int = None, suffix: str = "") -> str:
    try:
        from PIL import Image
        try:
            ar_w, ar_h = map(int, aspect_ratio.split(":"))
            target_ar = ar_w / ar_h
        except Exception:
            target_ar = 16 / 9
            ar_w, ar_h = 16, 9
            
        img = Image.open(image_path)
        orig_w, orig_h = img.size
        orig_ar = orig_w / orig_h
        
        if abs(orig_ar - target_ar) > 0.01:
            if orig_ar > target_ar:
                new_w = int(orig_h * target_ar)
                left = (orig_w - new_w) // 2
                img = img.crop((left, 0, left + new_w, orig_h))
            else:
                new_h = int(orig_w / target_ar)
                top = (orig_h - new_h) // 2
                img = img.crop((0, top, orig_w, top + new_h))
            
        if not target_w or not target_h:
            if ar_w == 16 and ar_h == 9:
                target_w, target_h = 1280, 720
            elif ar_w == 9 and ar_h == 16:
                target_w, target_h = 720, 1280
            elif ar_w == 1 and ar_h == 1:
                target_w, target_h = 1024, 1024
            else:
                target_w, target_h = 1280, 720
                
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        temp_file = os.path.join(os.path.dirname(image_path), f"temp_vgen_input{suffix}.jpg")
        img_resized.save(temp_file, "JPEG", quality=95)
        return temp_file
    except Exception:
        return image_path

# ==============================================================================
# MAIN EXECUTION FUNCTIONS & CUSTOM ERRORS
# ==============================================================================

class CreditExhaustedError(Exception):
    """Raised when an account runs out of credits (Forbidden / Fail to verify credit)."""
    pass

class AuthExpiredError(Exception):
    """Raised when a member token is invalid or expired (Unauthorized)."""
    pass


# ==============================================================================
# CYBERLINK LIVE ACTION CREDITS MAPPING (Direct from CyberLink Featurelist SID ae44600d)
# ==============================================================================
CYBERLINK_ACTION_CREDITS = json.loads(
    r"""{"genvideo_1_sec_alibaba_happyhorse1.0_enable_1080p":8,"genvideo_1_sec_alibaba_happyhorse1.0_none_1080p":8,"genvideo_1_sec_bytedance_seedance2.0std_enable_720p":10,"genvideo_1_sec_bytedance_seedance2.0std_none_720p":10,"genvideo_1_sec_kling_o3pro_enable_1080p":6,"genvideo_1_sec_kling_o3pro_none_1080p":5,"genimage_1_img_google_gemini3pro_custom":3,"genimage_1_img_google_gemini3pro_template":6,"genimage_1_img_google_gemini3pro_template_none":6,"genimage_1_img_openai_gptimage2_custom":6,"genimage_1_img_openai_gptimage2_custom_enable":3,"genimage_1_img_openai_gptimage2_custom_none":3,"genimage_1_img_openai_gptimage2_template":6,"genimage_1_img_openai_gptimage2_template_none":3,"genvideo_1_sec_bytedance_seedance2.5std_enable_enable_720p":14,"genvideo_1_sec_bytedance_seedance2.5std_enable_none_720p":14,"genvideo_1_sec_bytedance_seedance2.5std_none_enable_720p":14,"genvideo_1_sec_bytedance_seedance2.5std_none_none_720p":14,"genimage_1_img_google_gemini3.1flash_custom_none":3,"genimage_1_img_google_gemini3.1flash_template_none":8,"genimage_1_img_google_gemini3pro_custom_enable":6,"genimage_1_img_openai_gptimage2.5sunburst_template_none":8,"genvideo_1_video_cyberlink_remotion_export":1,"genvideo_60_img_cyberlink_remotion_edit":5,"genimage_1_img_cyberlink_fluxdev1_none":1,"genimage_1_img_google_gemini3pro_enable":6,"genimage_1_img_openai_gptimage2_enable":5,"genimage_1_img_google_gemini2.5flash_template_none":3,"genimage_1_img_google_gemini3.1flash_custom_enable_pet":6,"genimage_1_img_google_gemini3.1flash_custom_none_pet":6,"genimage_1_img_google_gemini3pro_template_none_pet":6,"genimage_1_img_kling_o1_custom_enable":6,"genimage_1_img_kling_o1_custom_none":3,"genimage_1_img_kling_o1_template_none":3,"genimage_1_img_kling_o3_custom_enable":6,"genimage_1_img_kling_o3_custom_none":6,"genimage_1_img_alibaba_qwenimage3.0_enable":3,"genimage_1_img_alibaba_qwenimage3.0_none":3,"genimage_1_img_alibaba_qwenimage3.0pro_enable":5,"genimage_1_img_alibaba_qwenimage3.0pro_none":5,"genimage_1_img_blackforest_flux2pro":5,"genimage_1_img_blackforest_flux2pro_enable":6,"genimage_1_img_blackforest_flux2pro_none":3,"genimage_1_img_bytedance_seedream5.0lite_enable":3,"genimage_1_img_bytedance_seedream5.0lite_none":3,"genimage_1_img_bytedance_seedream5.0pro_enable":5,"genimage_1_img_bytedance_seedream5.0pro_none":5,"genimage_1_img_cyberlink_qwen2511_enable":2,"genimage_1_img_cyberlink_qwen2511_none":2,"genimage_1_img_google_gemini2.5flash":2,"genimage_1_img_google_gemini2.5flash_enable":2,"genimage_1_img_google_gemini2.5flash_none":2,"genimage_1_img_google_gemini3.1flash_enable":5,"genimage_1_img_google_gemini3.1flashlite_enable":2,"genimage_1_img_google_gemini3.1flashlite_none":2,"genimage_1_img_google_gemini3.1flash_none":5,"genimage_1_img_google_gemini3pro":6,"genimage_1_img_google_gemini3pro_none":6,"genimage_1_img_google_gemininanobanana2.1_enable":4,"genimage_1_img_google_gemininanobanana2.1_none":4,"genimage_1_img_kling_o3_enable":3,"genimage_1_img_kling_o3_none":3,"genimage_1_img_openai_gptimage1.5":3,"genimage_1_img_openai_gptimage2.5flare_enable":5,"genimage_1_img_openai_gptimage2.5flare_none":5,"genimage_1_img_openai_gptimage2.5sunburst_enable":5,"genimage_1_img_openai_gptimage2.5sunburst_none":5,"genimage_1_img_openai_gptimage2_none":5,"genvideo_1_sec_alibaba_custom_happyhorse1.0_enable_single_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.0_enable_single_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.0_enable_startend_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.0_enable_startend_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.0_none_single_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.0_none_single_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.0_none_startend_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.0_none_startend_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.1_enable_single_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.1_enable_single_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.1_enable_startend_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.1_enable_startend_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.1_none_single_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.1_none_single_720p":5,"genvideo_1_sec_alibaba_custom_happyhorse1.1_none_startend_1080p":8,"genvideo_1_sec_alibaba_custom_happyhorse1.1_none_startend_720p":5,"genvideo_1_sec_alibaba_custom_wan2.7_enable_single_1080p":8,"genvideo_1_sec_alibaba_custom_wan2.7_enable_single_720p":5,"genvideo_1_sec_alibaba_custom_wan2.7_enable_startend_1080p":8,"genvideo_1_sec_alibaba_custom_wan2.7_enable_startend_720p":5,"genvideo_1_sec_alibaba_custom_wan2.7_none_single_1080p":8,"genvideo_1_sec_alibaba_custom_wan2.7_none_single_720p":5,"genvideo_1_sec_alibaba_custom_wan2.7_none_startend_1080p":8,"genvideo_1_sec_alibaba_custom_wan2.7_none_startend_720p":5,"genvideo_1_sec_alibaba_custom_wan3.0_enable_single_1080p":8,"genvideo_1_sec_alibaba_custom_wan3.0_enable_single_480p":2,"genvideo_1_sec_alibaba_custom_wan3.0_enable_single_720p":4,"genvideo_1_sec_alibaba_custom_wan3.0_enable_startend_1080p":8,"genvideo_1_sec_alibaba_custom_wan3.0_enable_startend_480p":2,"genvideo_1_sec_alibaba_custom_wan3.0_enable_startend_720p":4,"genvideo_1_sec_alibaba_custom_wan3.0_none_single_1080p":8,"genvideo_1_sec_alibaba_custom_wan3.0_none_single_480p":2,"genvideo_1_sec_alibaba_custom_wan3.0_none_single_720p":4,"genvideo_1_sec_alibaba_custom_wan3.0_none_startend_1080p":8,"genvideo_1_sec_alibaba_custom_wan3.0_none_startend_480p":2,"genvideo_1_sec_alibaba_custom_wan3.0_none_startend_720p":4,"genvideo_1_sec_blackforest_custom_flux3_enable_single_1080p":15,"genvideo_1_sec_blackforest_custom_flux3_enable_single_2k":20,"genvideo_1_sec_blackforest_custom_flux3_enable_single_4k":35,"genvideo_1_sec_blackforest_custom_flux3_enable_single_720p":9,"genvideo_1_sec_blackforest_custom_flux3_enable_startend_1080p":15,"genvideo_1_sec_blackforest_custom_flux3_enable_startend_2k":20,"genvideo_1_sec_blackforest_custom_flux3_enable_startend_4k":35,"genvideo_1_sec_blackforest_custom_flux3_enable_startend_720p":9,"genvideo_1_sec_blackforest_custom_flux3_none_single_1080p":15,"genvideo_1_sec_blackforest_custom_flux3_none_single_2k":20,"genvideo_1_sec_blackforest_custom_flux3_none_single_4k":35,"genvideo_1_sec_blackforest_custom_flux3_none_single_720p":9,"genvideo_1_sec_blackforest_custom_flux3_none_startend_1080p":15,"genvideo_1_sec_blackforest_custom_flux3_none_startend_2k":20,"genvideo_1_sec_blackforest_custom_flux3_none_startend_4k":35,"genvideo_1_sec_blackforest_custom_flux3_none_startend_720p":9,"genvideo_1_sec_bytedance_custom_seedance2.0fast_enable_single_480p":4,"genvideo_1_sec_bytedance_custom_seedance2.0fast_enable_single_720p":8,"genvideo_1_sec_bytedance_custom_seedance2.0fast_enable_startend_480p":4,"genvideo_1_sec_bytedance_custom_seedance2.0fast_enable_startend_720p":8,"genvideo_1_sec_bytedance_custom_seedance2.0fast_none_single_480p":4,"genvideo_1_sec_bytedance_custom_seedance2.0fast_none_single_720p":8,"genvideo_1_sec_bytedance_custom_seedance2.0fast_none_startend_480p":4,"genvideo_1_sec_bytedance_custom_seedance2.0fast_none_startend_720p":8,"genvideo_1_sec_bytedance_custom_seedance2.0mini_enable_single_480p":3,"genvideo_1_sec_bytedance_custom_seedance2.0mini_enable_single_720p":5,"genvideo_1_sec_bytedance_custom_seedance2.0mini_enable_startend_480p":3,"genvideo_1_sec_bytedance_custom_seedance2.0mini_enable_startend_720p":5,"genvideo_1_sec_bytedance_custom_seedance2.0mini_none_single_480p":3,"genvideo_1_sec_bytedance_custom_seedance2.0mini_none_single_720p":5,"genvideo_1_sec_bytedance_custom_seedance2.0mini_none_startend_480p":3,"genvideo_1_sec_bytedance_custom_seedance2.0mini_none_startend_720p":5,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_single_1080p":20,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_single_480p":5,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_single_4K":34,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_single_720p":10,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_startend_1080p":20,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_startend_480p":5,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_startend_4K":34,"genvideo_1_sec_bytedance_custom_seedance2.0std_enable_startend_720p":10,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_single_1080p":20,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_single_480p":5,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_single_4K":34,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_single_720p":10,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_startend_1080p":20,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_startend_480p":5,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_startend_4K":34,"genvideo_1_sec_bytedance_custom_seedance2.0std_none_startend_720p":10,"genvideo_1_sec_bytedance_custom_seedance2.5std_enable_single_1080p":28,"genvideo_1_sec_bytedance_custom_seedance2.5std_enable_single_480p":6,"genvideo_1_sec_bytedance_custom_seedance2.5std_enable_single_720p":14,"genvideo_1_sec_bytedance_custom_seedance2.5std_enable_startend_1080p":28,"genvideo_1_sec_bytedance_custom_seedance2.5std_enable_startend_480p":6,"genvideo_1_sec_bytedance_custom_seedance2.5std_enable_startend_720p":14,"genvideo_1_sec_bytedance_custom_seedance2.5std_none_single_1080p":28,"genvideo_1_sec_bytedance_custom_seedance2.5std_none_single_480p":6,"genvideo_1_sec_bytedance_custom_seedance2.5std_none_single_720p":14,"genvideo_1_sec_bytedance_custom_seedance2.5std_none_startend_1080p":28,"genvideo_1_sec_bytedance_custom_seedance2.5std_none_startend_480p":6,"genvideo_1_sec_bytedance_custom_seedance2.5std_none_startend_720p":14,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_single_1080p":8,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_single_360p":2,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_single_4k":15,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_single_720p":5,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_startend_1080p":8,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_startend_360p":2,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_startend_4k":15,"genvideo_1_sec_google_custom_geminiomni1.1flash_enable_startend_720p":5,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_single_1080p":8,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_single_360p":2,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_single_4k":15,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_single_720p":5,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_startend_1080p":8,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_startend_360p":2,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_startend_4k":15,"genvideo_1_sec_google_custom_geminiomni1.1flash_none_startend_720p":5,"genvideo_1_sec_google_custom_geminiomniflash_enable_single_720p":5,"genvideo_1_sec_google_custom_geminiomniflash_enable_startend_720p":5,"genvideo_1_sec_google_custom_geminiomniflash_none_single_720p":5,"genvideo_1_sec_google_custom_geminiomniflash_none_startend_720p":5,"genvideo_1_sec_google_custom_veo3.1fast_enable_single":8,"genvideo_1_sec_google_custom_veo3.1fast_enable_startend":8,"genvideo_1_sec_google_custom_veo3.1fast_none_single":5,"genvideo_1_sec_google_custom_veo3.1fast_none_startend":5,"genvideo_1_sec_google_custom_veo3.1lite_enable_single_1080p":5,"genvideo_1_sec_google_custom_veo3.1lite_enable_single_720p":3,"genvideo_1_sec_google_custom_veo3.1lite_enable_startend_1080p":5,"genvideo_1_sec_google_custom_veo3.1lite_enable_startend_720p":3,"genvideo_1_sec_google_custom_veo3.1lite_none_single_1080p":3,"genvideo_1_sec_google_custom_veo3.1lite_none_single_720p":2,"genvideo_1_sec_google_custom_veo3.1lite_none_startend_1080p":3,"genvideo_1_sec_google_custom_veo3.1lite_none_startend_720p":2,"genvideo_1_sec_google_custom_veo3.1std_enable_single":18,"genvideo_1_sec_google_custom_veo3.1std_enable_startend":18,"genvideo_1_sec_google_custom_veo3.1std_none_single":10,"genvideo_1_sec_google_custom_veo3.1std_none_startend":10,"genvideo_1_sec_kling_custom_2.5pro_enable_single":5,"genvideo_1_sec_kling_custom_2.5pro_enable_startend":5,"genvideo_1_sec_kling_custom_2.5pro_none_single":5,"genvideo_1_sec_kling_custom_2.5pro_none_startend":5,"genvideo_1_sec_kling_custom_2.5std_enable_single":3,"genvideo_1_sec_kling_custom_2.5std_none_single":3,"genvideo_1_sec_kling_custom_2.6pro_enable_single":8,"genvideo_1_sec_kling_custom_2.6pro_enable_startend":8,"genvideo_1_sec_kling_custom_2.6pro_none_single":5,"genvideo_1_sec_kling_custom_2.6pro_none_startend":5,"genvideo_1_sec_kling_custom_3.0pro_enable_single_1080p":8,"genvideo_1_sec_kling_custom_3.0pro_enable_startend_1080p":8,"genvideo_1_sec_kling_custom_3.0pro_none_single_1080p":5,"genvideo_1_sec_kling_custom_3.0pro_none_startend_1080p":5,"genvideo_1_sec_kling_custom_3.0std_enable_single_720p":6,"genvideo_1_sec_kling_custom_3.0std_enable_startend_720p":6,"genvideo_1_sec_kling_custom_3.0std_none_single_720p":4,"genvideo_1_sec_kling_custom_3.0std_none_startend_720p":4,"genvideo_1_sec_kling_custom_4.0flash_enable_single_720p":6,"genvideo_1_sec_kling_custom_4.0flash_enable_startend_720p":6,"genvideo_1_sec_kling_custom_4.0std_enable_single_1080p":14,"genvideo_1_sec_kling_custom_4.0std_enable_single_720p":9,"genvideo_1_sec_kling_custom_4.0std_enable_startend_1080p":14,"genvideo_1_sec_kling_custom_4.0std_enable_startend_720p":9,"genvideo_1_sec_kling_custom_o1pro_enable_single":6,"genvideo_1_sec_kling_custom_o1pro_enable_startend":6,"genvideo_1_sec_kling_custom_o1pro_none_single":6,"genvideo_1_sec_kling_custom_o1pro_none_startend":6,"genvideo_1_sec_kling_custom_o1std_enable_single":4,"genvideo_1_sec_kling_custom_o1std_enable_startend":4,"genvideo_1_sec_kling_custom_o1std_none_single":4,"genvideo_1_sec_kling_custom_o1std_none_startend":4,"genvideo_1_sec_kling_custom_o3pro_enable_single_1080p":6,"genvideo_1_sec_kling_custom_o3pro_enable_startend_1080p":6,"genvideo_1_sec_kling_custom_o3pro_none_single_1080p":5,"genvideo_1_sec_kling_custom_o3pro_none_startend_1080p":5,"genvideo_1_sec_kling_custom_o3std_enable_single_720p":5,"genvideo_1_sec_kling_custom_o3std_enable_startend_720p":5,"genvideo_1_sec_kling_custom_o3std_none_single_720p":4,"genvideo_1_sec_kling_custom_o3std_none_startend_720p":4,"genvideo_1_sec_minimax_custom_minimaxh3_enable_single_2k":8,"genvideo_1_sec_minimax_custom_minimaxh3_enable_single_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3_enable_startend_2k":8,"genvideo_1_sec_minimax_custom_minimaxh3_enable_startend_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3max_enable_single_480p":3,"genvideo_1_sec_minimax_custom_minimaxh3max_enable_single_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3max_enable_startend_480p":3,"genvideo_1_sec_minimax_custom_minimaxh3max_enable_startend_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3max_none_single_480p":3,"genvideo_1_sec_minimax_custom_minimaxh3max_none_single_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3max_none_startend_480p":3,"genvideo_1_sec_minimax_custom_minimaxh3max_none_startend_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3_none_single_2k":8,"genvideo_1_sec_minimax_custom_minimaxh3_none_single_768p":5,"genvideo_1_sec_minimax_custom_minimaxh3_none_startend_2k":8,"genvideo_1_sec_minimax_custom_minimaxh3_none_startend_768p":5,"genvideo_1_sec_motivai_custom_pixverse6_enable_single_1080p":4,"genvideo_1_sec_motivai_custom_pixverse6_enable_single_720p":2,"genvideo_1_sec_motivai_custom_pixverse6_enable_startend_1080p":6,"genvideo_1_sec_motivai_custom_pixverse6_enable_startend_720p":3,"genvideo_1_sec_motivai_custom_pixverse6_none_single_1080p":4,"genvideo_1_sec_motivai_custom_pixverse6_none_single_720p":2,"genvideo_1_sec_motivai_custom_pixverse6_none_startend_1080p":6,"genvideo_1_sec_motivai_custom_pixverse6_none_startend_720p":3,"genvideo_1_sec_openai_custom_sora2pro_enable_single":18,"genvideo_1_sec_openai_custom_sora2pro_none_single":18,"genvideo_1_sec_openai_custom_sora2std_enable_single":6,"genvideo_1_sec_openai_custom_sora2std_none_single":6,"genvideo_1_sec_runway_custom_gen4turbo_enable_single":3,"genvideo_1_sec_runway_custom_gen4turbo_none_single":3,"genvideo_1_sec_vidu_custom_q2pro_enable_single":5,"genvideo_1_sec_vidu_custom_q2pro_enable_startend":5,"genvideo_1_sec_vidu_custom_q2pro_none_single":5,"genvideo_1_sec_vidu_custom_q2pro_none_startend":5,"genvideo_1_sec_vidu_custom_q2turbo_enable_single":3,"genvideo_1_sec_vidu_custom_q2turbo_enable_startend":3,"genvideo_1_sec_vidu_custom_q2turbo_none_single":3,"genvideo_1_sec_vidu_custom_q2turbo_none_startend":3,"genvideo_1_sec_vidu_custom_q3pro_enable_single_1080p":6,"genvideo_1_sec_vidu_custom_q3pro_enable_startend_1080p":6,"genvideo_1_sec_vidu_custom_q3pro_none_single_1080p":6,"genvideo_1_sec_vidu_custom_q3pro_none_startend_1080p":6,"genvideo_1_sec_vidu_custom_q3turbo_enable_single_720p":3,"genvideo_1_sec_vidu_custom_q3turbo_enable_startend_720p":3,"genvideo_1_sec_vidu_custom_q3turbo_none_single_720p":3,"genvideo_1_sec_vidu_custom_q3turbo_none_startend_720p":3,"genvideo_1_sec_vidu_custom_q4_enable_single_1080p":6,"genvideo_1_sec_vidu_custom_q4_enable_single_2k":9,"genvideo_1_sec_vidu_custom_q4_enable_single_4k":19,"genvideo_1_sec_vidu_custom_q4_enable_single_540p":2,"genvideo_1_sec_vidu_custom_q4_enable_single_720p":5,"genvideo_1_sec_vidu_custom_q4_enable_startend_1080p":6,"genvideo_1_sec_vidu_custom_q4_enable_startend_2k":9,"genvideo_1_sec_vidu_custom_q4_enable_startend_4k":19,"genvideo_1_sec_vidu_custom_q4_enable_startend_540p":2,"genvideo_1_sec_vidu_custom_q4_enable_startend_720p":5,"genvideo_1_sec_vidu_custom_q4_none_single_1080p":6,"genvideo_1_sec_vidu_custom_q4_none_single_2k":9,"genvideo_1_sec_vidu_custom_q4_none_single_4k":19,"genvideo_1_sec_vidu_custom_q4_none_single_540p":2,"genvideo_1_sec_vidu_custom_q4_none_single_720p":5,"genvideo_1_sec_vidu_custom_q4_none_startend_1080p":6,"genvideo_1_sec_vidu_custom_q4_none_startend_2k":9,"genvideo_1_sec_vidu_custom_q4_none_startend_4k":19,"genvideo_1_sec_vidu_custom_q4_none_startend_540p":2,"genvideo_1_sec_vidu_custom_q4_none_startend_720p":5,"genimage_1_img_google_gemini3.1flash":5,"genvideo_1_sec_alibaba_happyhorse1.0_enable_720p":5,"genvideo_1_sec_alibaba_happyhorse1.0_none_720p":5,"genvideo_1_sec_alibaba_happyhorse1.1_enable_1080p":8,"genvideo_1_sec_alibaba_happyhorse1.1_enable_720p":5,"genvideo_1_sec_alibaba_happyhorse1.1_none_1080p":8,"genvideo_1_sec_alibaba_happyhorse1.1_none_720p":5,"genvideo_1_sec_alibaba_wan2.7_enable_1080p":8,"genvideo_1_sec_alibaba_wan2.7_enable_720p":5,"genvideo_1_sec_alibaba_wan2.7_none_1080p":8,"genvideo_1_sec_alibaba_wan2.7_none_720p":5,"genvideo_1_sec_alibaba_wan3.0_enable_1080p":8,"genvideo_1_sec_alibaba_wan3.0_enable_480p":2,"genvideo_1_sec_alibaba_wan3.0_enable_720p":4,"genvideo_1_sec_alibaba_wan3.0_none_1080p":8,"genvideo_1_sec_alibaba_wan3.0_none_480p":2,"genvideo_1_sec_alibaba_wan3.0_none_720p":4,"genvideo_1_sec_blackforest_flux3_enable_1080p":15,"genvideo_1_sec_blackforest_flux3_enable_2k":20,"genvideo_1_sec_blackforest_flux3_enable_4k":35,"genvideo_1_sec_blackforest_flux3_enable_720p":9,"genvideo_1_sec_blackforest_flux3_none_1080p":15,"genvideo_1_sec_blackforest_flux3_none_2k":20,"genvideo_1_sec_blackforest_flux3_none_4k":35,"genvideo_1_sec_blackforest_flux3_none_720p":9,"genvideo_1_sec_bytedance_seedance2.0fast_enable_480p":4,"genvideo_1_sec_bytedance_seedance2.0fast_enable_480p_motionbrush":4,"genvideo_1_sec_bytedance_seedance2.0fast_enable_720p":8,"genvideo_1_sec_bytedance_seedance2.0fast_enable_720p_motionbrush":8,"genvideo_1_sec_bytedance_seedance2.0fast_none_480p":4,"genvideo_1_sec_bytedance_seedance2.0fast_none_480p_motionbrush":4,"genvideo_1_sec_bytedance_seedance2.0fast_none_720p":8,"genvideo_1_sec_bytedance_seedance2.0fast_none_720p_motionbrush":8,"genvideo_1_sec_bytedance_seedance2.0mini_enable_480p":3,"genvideo_1_sec_bytedance_seedance2.0mini_enable_480p_motionbrush":3,"genvideo_1_sec_bytedance_seedance2.0mini_enable_720p":5,"genvideo_1_sec_bytedance_seedance2.0mini_enable_720p_motionbrush":5,"genvideo_1_sec_bytedance_seedance2.0mini_none_480p":3,"genvideo_1_sec_bytedance_seedance2.0mini_none_480p_motionbrush":3,"genvideo_1_sec_bytedance_seedance2.0mini_none_720p":5,"genvideo_1_sec_bytedance_seedance2.0mini_none_720p_motionbrush":5,"genvideo_1_sec_bytedance_seedance2.0std_enable_1080p":20,"genvideo_1_sec_bytedance_seedance2.0std_enable_1080p_motionbrush":20,"genvideo_1_sec_bytedance_seedance2.0std_enable_480p":5,"genvideo_1_sec_bytedance_seedance2.0std_enable_480p_motionbrush":5,"genvideo_1_sec_bytedance_seedance2.0std_enable_4K":34,"genvideo_1_sec_bytedance_seedance2.0std_enable_4k_motionbrush":34,"genvideo_1_sec_bytedance_seedance2.0std_enable_720p_motionbrush":10,"genvideo_1_sec_bytedance_seedance2.0std_none_1080p":20,"genvideo_1_sec_bytedance_seedance2.0std_none_1080p_motionbrush":20,"genvideo_1_sec_bytedance_seedance2.0std_none_480p":5,"genvideo_1_sec_bytedance_seedance2.0std_none_480p_motionbrush":5,"genvideo_1_sec_bytedance_seedance2.0std_none_4K":34,"genvideo_1_sec_bytedance_seedance2.0std_none_4k_motionbrush":34,"genvideo_1_sec_bytedance_seedance2.0std_none_720p_motionbrush":10,"genvideo_1_sec_bytedance_seedance2.5std_enable_1080p":28,"genvideo_1_sec_bytedance_seedance2.5std_enable_480p":6,"genvideo_1_sec_bytedance_seedance2.5std_enable_720p":14,"genvideo_1_sec_bytedance_seedance2.5std_none_1080p":28,"genvideo_1_sec_bytedance_seedance2.5std_none_480p":6,"genvideo_1_sec_bytedance_seedance2.5std_none_720p":14,"genvideo_1_sec_google_geminiomni1.1flash_enable_1080p":8,"genvideo_1_sec_google_geminiomni1.1flash_enable_360p":2,"genvideo_1_sec_google_geminiomni1.1flash_enable_4k":15,"genvideo_1_sec_google_geminiomni1.1flash_enable_720p":5,"genvideo_1_sec_google_geminiomni1.1flash_none_1080p":8,"genvideo_1_sec_google_geminiomni1.1flash_none_360p":2,"genvideo_1_sec_google_geminiomni1.1flash_none_4k":15,"genvideo_1_sec_google_geminiomni1.1flash_none_720p":5,"genvideo_1_sec_google_geminiomniflash_enable_720p":5,"genvideo_1_sec_google_geminiomniflash_none_720p":5,"genvideo_1_sec_kling_4.0flash_enable_720p":6,"genvideo_1_sec_kling_4.0std_enable_1080p":14,"genvideo_1_sec_kling_4.0std_enable_720p":9,"genvideo_1_sec_kling_o34k_enable_4k":14,"genvideo_1_sec_kling_o34k_none_4k":14,"genvideo_1_sec_kling_o3std_enable_720p":5,"genvideo_1_sec_kling_o3std_none_720p":4,"genvideo_1_sec_minimax_minimaxh3_enable_2k":8,"genvideo_1_sec_minimax_minimaxh3_enable_768p":5,"genvideo_1_sec_minimax_minimaxh3max_enable_480p":3,"genvideo_1_sec_minimax_minimaxh3max_enable_768p":5,"genvideo_1_sec_minimax_minimaxh3max_none_480p":3,"genvideo_1_sec_minimax_minimaxh3max_none_768p":5,"genvideo_1_sec_minimax_minimaxh3_none_2k":8,"genvideo_1_sec_minimax_minimaxh3_none_768p":5,"genvideo_1_sec_motivai_pixverse6_enable_1080p":6,"genvideo_1_sec_motivai_pixverse6_enable_540p":2,"genvideo_1_sec_motivai_pixverse6_enable_720p":3,"genvideo_1_sec_motivai_pixverse6_none_1080p":4,"genvideo_1_sec_motivai_pixverse6_none_540p":1,"genvideo_1_sec_motivai_pixverse6_none_720p":2,"genvideo_1_sec_vidu_q3_enable_1080p":5,"genvideo_1_sec_vidu_q3_enable_540p":3,"genvideo_1_sec_vidu_q3_enable_720p":4,"genvideo_1_sec_vidu_q3mix_enable_1080p":9,"genvideo_1_sec_vidu_q3mix_enable_720p":7,"genvideo_1_sec_vidu_q3mix_none_1080p":9,"genvideo_1_sec_vidu_q3mix_none_720p":7,"genvideo_1_sec_vidu_q3_none_1080p":5,"genvideo_1_sec_vidu_q3_none_540p":3,"genvideo_1_sec_vidu_q3_none_720p":4,"genvideo_1_sec_vidu_q3turbo_enable_1080p":4,"genvideo_1_sec_vidu_q3turbo_enable_540p":2,"genvideo_1_sec_vidu_q3turbo_enable_720p":3,"genvideo_1_sec_vidu_q3turbo_none_1080p":4,"genvideo_1_sec_vidu_q3turbo_none_540p":2,"genvideo_1_sec_vidu_q3turbo_none_720p":3,"genimage_1_img_alibaba_qwenimage3.0_enable_1k":2,"genimage_1_img_alibaba_qwenimage3.0_enable_2k":3,"genimage_1_img_alibaba_qwenimage3.0_none_1k":2,"genimage_1_img_alibaba_qwenimage3.0_none_2k":3,"genimage_1_img_alibaba_qwenimage3.0pro_enable_1k":3,"genimage_1_img_alibaba_qwenimage3.0pro_enable_2k":5,"genimage_1_img_alibaba_qwenimage3.0pro_none_1k":3,"genimage_1_img_alibaba_qwenimage3.0pro_none_2k":5,"genimage_1_img_blackforest_flux2pro_enable_1k":3,"genimage_1_img_blackforest_flux2pro_enable_1K":3,"genimage_1_img_blackforest_flux2pro_enable_2k":6,"genimage_1_img_blackforest_flux2pro_enable_2K":6,"genimage_1_img_blackforest_flux2pro_none_1k":2,"genimage_1_img_blackforest_flux2pro_none_1K":2,"genimage_1_img_blackforest_flux2pro_none_2k":5,"genimage_1_img_blackforest_flux2pro_none_2K":5,"genimage_1_img_bytedance_seedream5.0lite_enable_2k":3,"genimage_1_img_bytedance_seedream5.0lite_enable_2K":3,"genimage_1_img_bytedance_seedream5.0lite_enable_3k":3,"genimage_1_img_bytedance_seedream5.0lite_enable_3K":3,"genimage_1_img_bytedance_seedream5.0lite_none_2k":3,"genimage_1_img_bytedance_seedream5.0lite_none_2K":3,"genimage_1_img_bytedance_seedream5.0lite_none_3k":3,"genimage_1_img_bytedance_seedream5.0lite_none_3K":3,"genimage_1_img_bytedance_seedream5.0pro_enable_1k":3,"genimage_1_img_bytedance_seedream5.0pro_enable_1K":3,"genimage_1_img_bytedance_seedream5.0pro_enable_2k":5,"genimage_1_img_bytedance_seedream5.0pro_enable_2K":5,"genimage_1_img_bytedance_seedream5.0pro_none_1k":3,"genimage_1_img_bytedance_seedream5.0pro_none_1K":3,"genimage_1_img_bytedance_seedream5.0pro_none_2k":5,"genimage_1_img_bytedance_seedream5.0pro_none_2K":5,"genimage_1_img_cyberlink_fluxdev1_none_1k":1,"genimage_1_img_cyberlink_fluxdev1_none_1K":1,"genimage_1_img_cyberlink_stablediffusion_enable":1,"genimage_1_img_cyberlink_stablediffusion_enable_1k":1,"genimage_1_img_cyberlink_stablediffusion_enable_1K":1,"genimage_1_img_cyberlink_stablediffusion_none":1,"genimage_1_img_cyberlink_stablediffusion_none_1k":1,"genimage_1_img_cyberlink_stablediffusion_none_1K":1,"genimage_1_img_cyberlink_zimageturbo_none":2,"genimage_1_img_cyberlink_zimageturbo_none_1k":1,"genimage_1_img_cyberlink_zimageturbo_none_1K":1,"genimage_1_img_cyberlink_zimageturbo_none_2k":2,"genimage_1_img_cyberlink_zimageturbo_none_2K":2,"genimage_1_img_google_gemini2.5flash_enable_1k":2,"genimage_1_img_google_gemini2.5flash_enable_1K":2,"genimage_1_img_google_gemini2.5flash_none_1k":2,"genimage_1_img_google_gemini2.5flash_none_1K":2,"genimage_1_img_google_gemini3.1flash_enable_1k":3,"genimage_1_img_google_gemini3.1flash_enable_1K":3,"genimage_1_img_google_gemini3.1flash_enable_2k":5,"genimage_1_img_google_gemini3.1flash_enable_2K":5,"genimage_1_img_google_gemini3.1flash_enable_4k":7,"genimage_1_img_google_gemini3.1flash_enable_4K":7,"genimage_1_img_google_gemini3.1flashlite_enable_1k":2,"genimage_1_img_google_gemini3.1flashlite_enable_1K":2,"genimage_1_img_google_gemini3.1flashlite_none_1k":2,"genimage_1_img_google_gemini3.1flashlite_none_1K":2,"genimage_1_img_google_gemini3.1flash_none_1k":3,"genimage_1_img_google_gemini3.1flash_none_1K":3,"genimage_1_img_google_gemini3.1flash_none_2k":5,"genimage_1_img_google_gemini3.1flash_none_2K":5,"genimage_1_img_google_gemini3.1flash_none_4k":7,"genimage_1_img_google_gemini3.1flash_none_4K":7,"genimage_1_img_google_gemini3pro_enable_1k":6,"genimage_1_img_google_gemini3pro_enable_1K":6,"genimage_1_img_google_gemini3pro_enable_2k":6,"genimage_1_img_google_gemini3pro_enable_2K":6,"genimage_1_img_google_gemini3pro_enable_4k":12,"genimage_1_img_google_gemini3pro_enable_4K":12,"genimage_1_img_google_gemini3pro_none_1k":6,"genimage_1_img_google_gemini3pro_none_1K":6,"genimage_1_img_google_gemini3pro_none_2k":6,"genimage_1_img_google_gemini3pro_none_2K":6,"genimage_1_img_google_gemini3pro_none_4k":12,"genimage_1_img_google_gemini3pro_none_4K":12,"genimage_1_img_google_gemininanobanana2.1_enable_1k":3,"genimage_1_img_google_gemininanobanana2.1_enable_2k":4,"genimage_1_img_google_gemininanobanana2.1_enable_4k":8,"genimage_1_img_google_gemininanobanana2.1_none_1k":3,"genimage_1_img_google_gemininanobanana2.1_none_2k":4,"genimage_1_img_google_gemininanobanana2.1_none_4k":8,"genimage_1_img_kling_o1_enable":3,"genimage_1_img_kling_o1_enable_1k":3,"genimage_1_img_kling_o1_enable_1K":3,"genimage_1_img_kling_o1_enable_2k":3,"genimage_1_img_kling_o1_enable_2K":3,"genimage_1_img_kling_o1_enable_4k":5,"genimage_1_img_kling_o1_enable_4K":5,"genimage_1_img_kling_o1_none":3,"genimage_1_img_kling_o1_none_1k":3,"genimage_1_img_kling_o1_none_1K":3,"genimage_1_img_kling_o1_none_2k":3,"genimage_1_img_kling_o1_none_2K":3,"genimage_1_img_kling_o1_none_4k":5,"genimage_1_img_kling_o3_enable_1k":3,"genimage_1_img_kling_o3_enable_1K":3,"genimage_1_img_kling_o3_enable_2k":3,"genimage_1_img_kling_o3_enable_2K":3,"genimage_1_img_kling_o3_enable_4k":5,"genimage_1_img_kling_o3_enable_4K":5,"genimage_1_img_kling_o3_none_1k":3,"genimage_1_img_kling_o3_none_1K":3,"genimage_1_img_kling_o3_none_2k":3,"genimage_1_img_kling_o3_none_2K":3,"genimage_1_img_kling_o3_none_4k":5,"genimage_1_img_kling_o3_none_4K":5,"genimage_1_img_openai_gptimage1.5_enable":3,"genimage_1_img_openai_gptimage1.5_enable_1k":3,"genimage_1_img_openai_gptimage1.5_enable_1K":3,"genimage_1_img_openai_gptimage1.5_none":3,"genimage_1_img_openai_gptimage1.5_none_1k":3,"genimage_1_img_openai_gptimage1.5_none_1K":3,"genimage_1_img_openai_gptimage1_enable":2,"genimage_1_img_openai_gptimage1_enable_1k":2,"genimage_1_img_openai_gptimage1_enable_1K":2,"genimage_1_img_openai_gptimage1_none":2,"genimage_1_img_openai_gptimage1_none_1k":2,"genimage_1_img_openai_gptimage1_none_1K":2,"genimage_1_img_openai_gptimage2.5flare_enable_1k":3,"genimage_1_img_openai_gptimage2.5flare_enable_1K":3,"genimage_1_img_openai_gptimage2.5flare_enable_2k":6,"genimage_1_img_openai_gptimage2.5flare_enable_2K":6,"genimage_1_img_openai_gptimage2.5flare_none_1k":3,"genimage_1_img_openai_gptimage2.5flare_none_1K":3,"genimage_1_img_openai_gptimage2.5flare_none_2k":6,"genimage_1_img_openai_gptimage2.5flare_none_2K":6,"genimage_1_img_openai_gptimage2.5sunburst_enable_1k":3,"genimage_1_img_openai_gptimage2.5sunburst_enable_1K":3,"genimage_1_img_openai_gptimage2.5sunburst_enable_2k":6,"genimage_1_img_openai_gptimage2.5sunburst_enable_2K":6,"genimage_1_img_openai_gptimage2.5sunburst_none_1k":3,"genimage_1_img_openai_gptimage2.5sunburst_none_1K":3,"genimage_1_img_openai_gptimage2.5sunburst_none_2k":6,"genimage_1_img_openai_gptimage2.5sunburst_none_2K":6,"genimage_1_img_openai_gptimage2_enable_1k":3,"genimage_1_img_openai_gptimage2_enable_1K":3,"genimage_1_img_openai_gptimage2_enable_2k":6,"genimage_1_img_openai_gptimage2_enable_2K":6,"genimage_1_img_openai_gptimage2_none_1k":3,"genimage_1_img_openai_gptimage2_none_1K":3,"genimage_1_img_openai_gptimage2_none_2k":6,"genimage_1_img_openai_gptimage2_none_2K":6,"genvideo_1_sec_bytedance_seedance2.0fast_enable_none_1080p":18,"genvideo_1_sec_bytedance_seedance2.0fast_none_none_1080p":18,"genvideo_1_sec_google_veo3.1fast_enable_1080p":9,"genvideo_1_sec_google_veo3.1fast_enable_4k":16,"genvideo_1_sec_google_veo3.1fast_enable_720p":7,"genvideo_1_sec_google_veo3.1fast_none_1080p":7,"genvideo_1_sec_google_veo3.1fast_none_4k":14,"genvideo_1_sec_google_veo3.1fast_none_720p":5,"genvideo_1_sec_google_veo3.1lite_enable_1080p":5,"genvideo_1_sec_google_veo3.1lite_enable_720p":3,"genvideo_1_sec_google_veo3.1lite_none_1080p":3,"genvideo_1_sec_google_veo3.1lite_none_720p":2,"genvideo_1_sec_google_veo3.1std_enable_1080p":18,"genvideo_1_sec_google_veo3.1std_enable_4k":30,"genvideo_1_sec_google_veo3.1std_enable_720p":18,"genvideo_1_sec_google_veo3.1std_none_1080p":10,"genvideo_1_sec_google_veo3.1std_none_4k":20,"genvideo_1_sec_google_veo3.1std_none_720p":10,"genvideo_1_sec_kling_2.5pro_enable_1080p":4,"genvideo_1_sec_kling_2.5pro_none_1080p":4,"genvideo_1_sec_kling_2.5std_enable_720p":2,"genvideo_1_sec_kling_2.5std_none_720p":2,"genvideo_1_sec_kling_2.6pro_enable_1080p":8,"genvideo_1_sec_kling_2.6pro_none_1080p":4,"genvideo_1_sec_kling_3.04k_enable_4k":14,"genvideo_1_sec_kling_3.04k_none_4k":14,"genvideo_1_sec_kling_3.0pro_enable_1080p":8,"genvideo_1_sec_kling_3.0pro_none_1080p":5,"genvideo_1_sec_kling_3.0std_enable_720p":6,"genvideo_1_sec_kling_3.0std_none_720p":4,"genvideo_1_sec_kling_o3pro_enable_enable_720p":6,"genvideo_1_sec_kling_o3pro_none_enable_720p":4,"genvideo_1_sec_kling_o3std_enable_none_1080p":8,"genvideo_1_sec_kling_o3std_none_none_1080p":5,"genvideo_1_sec_openai_sora2_enable_720p":6,"genvideo_1_sec_openai_sora2_none_720p":6,"genvideo_1_sec_openai_sora2pro_enable_1024p":22,"genvideo_1_sec_openai_sora2pro_enable_1080p":28,"genvideo_1_sec_openai_sora2pro_enable_720p":16,"genvideo_1_sec_openai_sora2pro_none_1024p":22,"genvideo_1_sec_openai_sora2pro_none_1080p":28,"genvideo_1_sec_openai_sora2pro_none_720p":16,"genvideo_1_sec_vidu_q2_enable_1080p":3,"genvideo_1_sec_vidu_q2_enable_540p":1,"genvideo_1_sec_vidu_q2_enable_720p":2,"genvideo_1_sec_vidu_q2_none_1080p":3,"genvideo_1_sec_vidu_q2_none_540p":1,"genvideo_1_sec_vidu_q2_none_720p":2,"genvideo_1_sec_vidu_q3pro_enable_1080p":6,"genvideo_1_sec_vidu_q3pro_enable_540p":3,"genvideo_1_sec_vidu_q3pro_enable_720p":5,"genvideo_1_sec_vidu_q3pro_none_1080p":6,"genvideo_1_sec_vidu_q3pro_none_540p":3,"genvideo_1_sec_vidu_q3pro_none_720p":5,"genimage_1_img_google_gemini2.5flash_template":3,"genimage_1_img_openai_gptimage2.5sunburst_template":6,"genvideo_60_sec":2,"genvideo_1_sec_byteplus_pro_hd_1080p_120fps":16,"genvideo_1_sec_byteplus_pro_hd_1080p_30fps":4,"genvideo_1_sec_byteplus_pro_hd_1080p_60fps":8,"genvideo_1_sec_byteplus_pro_hd_4k_120fps":48,"genvideo_1_sec_byteplus_pro_hd_4k_30fps":12,"genvideo_1_sec_byteplus_pro_hd_4k_60fps":24,"genvideo_1_sec_byteplus_pro_hd_720p_120fps":8,"genvideo_1_sec_byteplus_pro_hd_720p_30fps":2,"genvideo_1_sec_byteplus_pro_hd_720p_60fps":4,"genvideo_1_sec_byteplus_pro_natural_1080p_120fps":16,"genvideo_1_sec_byteplus_pro_natural_1080p_30fps":4,"genvideo_1_sec_byteplus_pro_natural_1080p_60fps":8,"genvideo_1_sec_byteplus_pro_natural_4k_120fps":48,"genvideo_1_sec_byteplus_pro_natural_4k_30fps":12,"genvideo_1_sec_byteplus_pro_natural_4k_60fps":24,"genvideo_1_sec_byteplus_pro_natural_720p_120fps":8,"genvideo_1_sec_byteplus_pro_natural_720p_30fps":2,"genvideo_1_sec_byteplus_pro_natural_720p_60fps":4,"genvideo_1_sec_byteplus_std_hd_1080p_120fps":2,"genvideo_1_sec_byteplus_std_hd_1080p_30fps":2,"genvideo_1_sec_byteplus_std_hd_1080p_60fps":2,"genvideo_1_sec_byteplus_std_hd_4k_120fps":8,"genvideo_1_sec_byteplus_std_hd_4k_30fps":3,"genvideo_1_sec_byteplus_std_hd_4k_60fps":6,"genvideo_1_sec_byteplus_std_hd_720p_120fps":1,"genvideo_1_sec_byteplus_std_hd_720p_30fps":1,"genvideo_1_sec_byteplus_std_hd_720p_60fps":1,"genvideo_1_sec_byteplus_std_natural_1080p_120fps":2,"genvideo_1_sec_byteplus_std_natural_1080p_30fps":2,"genvideo_1_sec_byteplus_std_natural_1080p_60fps":2,"genvideo_1_sec_byteplus_std_natural_4k_120fps":8,"genvideo_1_sec_byteplus_std_natural_4k_30fps":3,"genvideo_1_sec_byteplus_std_natural_4k_60fps":6,"genvideo_1_sec_byteplus_std_natural_720p_120fps":1,"genvideo_1_sec_byteplus_std_natural_720p_30fps":1,"genvideo_1_sec_byteplus_std_natural_720p_60fps":1,"genvideo_1_sec_alibaba_happyhorse1.0_enable_enable_1080p":7,"genvideo_1_sec_alibaba_happyhorse1.0_enable_enable_720p":4,"genvideo_1_sec_alibaba_happyhorse1.0_enable_none_1080p":7,"genvideo_1_sec_alibaba_happyhorse1.0_enable_none_720p":4,"genvideo_1_sec_alibaba_happyhorse1.0_none_enable_1080p":7,"genvideo_1_sec_alibaba_happyhorse1.0_none_enable_720p":4,"genvideo_1_sec_alibaba_happyhorse1.0_none_none_1080p":7,"genvideo_1_sec_alibaba_happyhorse1.0_none_none_720p":4,"genvideo_1_sec_alibaba_wan2.7_enable_enable_1080p":5,"genvideo_1_sec_alibaba_wan2.7_enable_enable_720p":3,"genvideo_1_sec_alibaba_wan2.7_enable_none_1080p":5,"genvideo_1_sec_alibaba_wan2.7_enable_none_720p":3,"genvideo_1_sec_alibaba_wan2.7_none_enable_1080p":5,"genvideo_1_sec_alibaba_wan2.7_none_enable_720p":3,"genvideo_1_sec_alibaba_wan2.7_none_none_1080p":5,"genvideo_1_sec_alibaba_wan2.7_none_none_720p":3,"genvideo_1_sec_alibaba_wan3.0_enable_enable_1080p":8,"genvideo_1_sec_alibaba_wan3.0_enable_enable_480p":2,"genvideo_1_sec_alibaba_wan3.0_enable_enable_720p":4,"genvideo_1_sec_alibaba_wan3.0_enable_none_1080p":8,"genvideo_1_sec_alibaba_wan3.0_enable_none_480p":2,"genvideo_1_sec_alibaba_wan3.0_enable_none_720p":4,"genvideo_1_sec_alibaba_wan3.0_none_enable_1080p":8,"genvideo_1_sec_alibaba_wan3.0_none_enable_480p":2,"genvideo_1_sec_alibaba_wan3.0_none_enable_720p":4,"genvideo_1_sec_alibaba_wan3.0_none_none_1080p":8,"genvideo_1_sec_alibaba_wan3.0_none_none_480p":2,"genvideo_1_sec_alibaba_wan3.0_none_none_720p":4,"genvideo_1_sec_blackforest_flux3_enable_enable_1080p":25,"genvideo_1_sec_blackforest_flux3_enable_enable_2k":30,"genvideo_1_sec_blackforest_flux3_enable_enable_4k":40,"genvideo_1_sec_blackforest_flux3_enable_enable_720p":20,"genvideo_1_sec_blackforest_flux3_enable_none_1080p":25,"genvideo_1_sec_blackforest_flux3_enable_none_2k":30,"genvideo_1_sec_blackforest_flux3_enable_none_4k":40,"genvideo_1_sec_blackforest_flux3_enable_none_720p":20,"genvideo_1_sec_blackforest_flux3_none_enable_1080p":25,"genvideo_1_sec_blackforest_flux3_none_enable_2k":30,"genvideo_1_sec_blackforest_flux3_none_enable_4k":40,"genvideo_1_sec_blackforest_flux3_none_enable_720p":20,"genvideo_1_sec_blackforest_flux3_none_none_1080p":25,"genvideo_1_sec_blackforest_flux3_none_none_2k":30,"genvideo_1_sec_blackforest_flux3_none_none_4k":40,"genvideo_1_sec_blackforest_flux3_none_none_720p":20,"genvideo_1_sec_bytedance_seedance2.0fast_enable_enable_1080p":18,"genvideo_1_sec_bytedance_seedance2.0fast_enable_enable_480p":4,"genvideo_1_sec_bytedance_seedance2.0fast_enable_enable_4k":32,"genvideo_1_sec_bytedance_seedance2.0fast_enable_enable_720p":8,"genvideo_1_sec_bytedance_seedance2.0fast_enable_none_480p":4,"genvideo_1_sec_bytedance_seedance2.0fast_enable_none_4k":32,"genvideo_1_sec_bytedance_seedance2.0fast_enable_none_720p":8,"genvideo_1_sec_bytedance_seedance2.0fast_none_enable_1080p":18,"genvideo_1_sec_bytedance_seedance2.0fast_none_enable_480p":4,"genvideo_1_sec_bytedance_seedance2.0fast_none_enable_4k":32,"genvideo_1_sec_bytedance_seedance2.0fast_none_enable_720p":8,"genvideo_1_sec_bytedance_seedance2.0fast_none_none_480p":4,"genvideo_1_sec_bytedance_seedance2.0fast_none_none_4k":32,"genvideo_1_sec_bytedance_seedance2.0fast_none_none_720p":8,"genvideo_1_sec_bytedance_seedance2.0mini_enable_enable_1080p":18,"genvideo_1_sec_bytedance_seedance2.0mini_enable_enable_480p":3,"genvideo_1_sec_bytedance_seedance2.0mini_enable_enable_4k":32,"genvideo_1_sec_bytedance_seedance2.0mini_enable_enable_720p":5,"genvideo_1_sec_bytedance_seedance2.0mini_enable_none_1080p":18,"genvideo_1_sec_bytedance_seedance2.0mini_enable_none_480p":3,"genvideo_1_sec_bytedance_seedance2.0mini_enable_none_4k":32,"genvideo_1_sec_bytedance_seedance2.0mini_enable_none_720p":5,"genvideo_1_sec_bytedance_seedance2.0mini_none_enable_1080p":18,"genvideo_1_sec_bytedance_seedance2.0mini_none_enable_480p":3,"genvideo_1_sec_bytedance_seedance2.0mini_none_enable_4k":32,"genvideo_1_sec_bytedance_seedance2.0mini_none_enable_720p":5,"genvideo_1_sec_bytedance_seedance2.0mini_none_none_1080p":18,"genvideo_1_sec_bytedance_seedance2.0mini_none_none_480p":3,"genvideo_1_sec_bytedance_seedance2.0mini_none_none_4k":32,"genvideo_1_sec_bytedance_seedance2.0mini_none_none_720p":5,"genvideo_1_sec_bytedance_seedance2.0std_enable_enable_1080p":20,"genvideo_1_sec_bytedance_seedance2.0std_enable_enable_480p":5,"genvideo_1_sec_bytedance_seedance2.0std_enable_enable_4k":34,"genvideo_1_sec_bytedance_seedance2.0std_enable_enable_720p":10,"genvideo_1_sec_bytedance_seedance2.0std_enable_none_1080p":20,"genvideo_1_sec_bytedance_seedance2.0std_enable_none_480p":5,"genvideo_1_sec_bytedance_seedance2.0std_enable_none_4k":34,"genvideo_1_sec_bytedance_seedance2.0std_enable_none_720p":10,"genvideo_1_sec_bytedance_seedance2.0std_none_enable_1080p":20,"genvideo_1_sec_bytedance_seedance2.0std_none_enable_480p":5,"genvideo_1_sec_bytedance_seedance2.0std_none_enable_4k":34,"genvideo_1_sec_bytedance_seedance2.0std_none_enable_720p":10,"genvideo_1_sec_bytedance_seedance2.0std_none_none_1080p":20,"genvideo_1_sec_bytedance_seedance2.0std_none_none_480p":5,"genvideo_1_sec_bytedance_seedance2.0std_none_none_4k":34,"genvideo_1_sec_bytedance_seedance2.0std_none_none_720p":10,"genvideo_1_sec_bytedance_seedance2.5std_enable_enable_1080p":28,"genvideo_1_sec_bytedance_seedance2.5std_enable_enable_480p":6,"genvideo_1_sec_bytedance_seedance2.5std_enable_none_1080p":28,"genvideo_1_sec_bytedance_seedance2.5std_enable_none_480p":6,"genvideo_1_sec_bytedance_seedance2.5std_none_enable_1080p":28,"genvideo_1_sec_bytedance_seedance2.5std_none_enable_480p":6,"genvideo_1_sec_bytedance_seedance2.5std_none_none_1080p":28,"genvideo_1_sec_bytedance_seedance2.5std_none_none_480p":6,"genvideo_1_sec_google_geminiomni1.1flash_enable_enable_1080p":8,"genvideo_1_sec_google_geminiomni1.1flash_enable_enable_360p":2,"genvideo_1_sec_google_geminiomni1.1flash_enable_enable_4k":15,"genvideo_1_sec_google_geminiomni1.1flash_enable_enable_720p":5,"genvideo_1_sec_google_geminiomni1.1flash_enable_none_1080p":8,"genvideo_1_sec_google_geminiomni1.1flash_enable_none_360p":2,"genvideo_1_sec_google_geminiomni1.1flash_enable_none_4k":15,"genvideo_1_sec_google_geminiomni1.1flash_enable_none_720p":5,"genvideo_1_sec_kling_4.0flash_enable_enable_720p":8,"genvideo_1_sec_kling_4.0flash_enable_none_720p":8,"genvideo_1_sec_kling_4.0std_enable_enable_1080p":16,"genvideo_1_sec_kling_4.0std_enable_enable_720p":11,"genvideo_1_sec_kling_4.0std_enable_none_1080p":16,"genvideo_1_sec_kling_4.0std_enable_none_720p":11,"genvideo_1_sec_kling_o3pro_enable_enable_1080p":5,"genvideo_1_sec_kling_o3pro_enable_enable_4K":12,"genvideo_1_sec_kling_o3pro_enable_none_1080p":5,"genvideo_1_sec_kling_o3pro_enable_none_4K":12,"genvideo_1_sec_kling_o3pro_none_enable_1080p":5,"genvideo_1_sec_kling_o3pro_none_enable_4K":12,"genvideo_1_sec_kling_o3pro_none_none_1080p":5,"genvideo_1_sec_kling_o3pro_none_none_4K":12,"genvideo_1_sec_kling_o3std_enable_enable_720p":4,"genvideo_1_sec_kling_o3std_enable_none_720p":4,"genvideo_1_sec_kling_o3std_none_enable_720p":4,"genvideo_1_sec_kling_o3std_none_none_720p":4,"genvideo_1_sec_minimax_minimaxh3_enable_enable_2k":16,"genvideo_1_sec_minimax_minimaxh3_enable_enable_768p":10,"genvideo_1_sec_minimax_minimaxh3_enable_none_2k":16,"genvideo_1_sec_minimax_minimaxh3_enable_none_768p":10,"genvideo_1_sec_minimax_minimaxh3max_enable_enable_480p":7,"genvideo_1_sec_minimax_minimaxh3max_enable_enable_768p":14,"genvideo_1_sec_minimax_minimaxh3max_enable_none_480p":7,"genvideo_1_sec_minimax_minimaxh3max_enable_none_768p":14,"genvideo_1_sec_minimax_minimaxh3max_none_enable_480p":7,"genvideo_1_sec_minimax_minimaxh3max_none_enable_768p":14,"genvideo_1_sec_minimax_minimaxh3max_none_none_480p":7,"genvideo_1_sec_minimax_minimaxh3max_none_none_768p":14,"genvideo_1_sec_minimax_minimaxh3_none_enable_2k":16,"genvideo_1_sec_minimax_minimaxh3_none_enable_768p":10,"genvideo_1_sec_minimax_minimaxh3_none_none_2k":16,"genvideo_1_sec_minimax_minimaxh3_none_none_768p":10,"genvideo_1_sec_motivai_pixverse6_enable_enable_360p":1,"genvideo_1_sec_motivai_pixverse6_enable_enable_540p":2,"genvideo_1_sec_motivai_pixverse6_enable_enable_720p":3,"genvideo_1_sec_motivai_pixverse6_enable_none_360p":1,"genvideo_1_sec_motivai_pixverse6_enable_none_540p":2,"genvideo_1_sec_motivai_pixverse6_enable_none_720p":3,"genvideo_1_sec_motivai_pixverse6_none_enable_360p":1,"genvideo_1_sec_motivai_pixverse6_none_enable_540p":2,"genvideo_1_sec_motivai_pixverse6_none_enable_720p":3,"genvideo_1_sec_motivai_pixverse6_none_none_360p":1,"genvideo_1_sec_motivai_pixverse6_none_none_540p":2,"genvideo_1_sec_motivai_pixverse6_none_none_720p":3}"""
)


def resolve_video_action_and_credit(
    model_key: str,
    effect_mode: str = "TextToVideo",
    resolution: str = "720p",
    sound: str = "none",
    frame_mode: str = "single"
):
    """
    Verilen model, efekt modu, cozunurluk, ses ve frame moduna gore dogru action_id_str ve credit_cost dondurur.
    """
    model_data = VIDEO_MODELS_CONFIG.get(model_key, VIDEO_MODELS_CONFIG["seedance_2_0_fast"])
    action_id_sound = {"vendor": "enable", "none": "none", "auto": "enable", "on": "enable", "off": "none"}.get(str(sound).lower(), sound)
    if model_key == "kling_4_0" or model_data.get("always_sound_enable"):
        action_id_sound = "enable"

    if effect_mode == "ImageToVideo":
        overrides = model_data.get("action_id_i2v_overrides", {})
        if resolution in overrides:
            action_id_str = overrides[resolution].format(sound=action_id_sound, resolution=resolution, frame_mode=frame_mode)
        elif "action_id_i2v" in model_data:
            action_id_str = model_data["action_id_i2v"].format(sound=action_id_sound, resolution=resolution, frame_mode=frame_mode)
        else:
            overrides_t2v = model_data.get("action_id_overrides", {})
            if resolution in overrides_t2v:
                action_id_str = overrides_t2v[resolution].format(sound=action_id_sound, resolution=resolution)
            else:
                action_id_str = model_data["action_id"].format(sound=action_id_sound, resolution=resolution)
    else:
        overrides = model_data.get("action_id_overrides", {})
        if resolution in overrides:
            action_id_str = overrides[resolution].format(sound=action_id_sound, resolution=resolution)
        else:
            action_id_str = model_data["action_id"].format(sound=action_id_sound, resolution=resolution)

    credit_cost = None
    if action_id_str in CYBERLINK_ACTION_CREDITS:
        credit_cost = CYBERLINK_ACTION_CREDITS[action_id_str]
    else:
        credit_map = model_data.get("credit_map")
        if credit_map:
            credit_cost = credit_map.get((effect_mode, sound, frame_mode, resolution))
            if credit_cost is None:
                credit_cost = credit_map.get((effect_mode, sound, resolution))
            if credit_cost is None:
                credit_cost = credit_map.get((sound, resolution))
        if credit_cost is None:
            credit_cost = model_data.get("credit", 3)

    return action_id_str, credit_cost


def get_model_duration_config(model_key: str) -> dict:
    """
    Modelin sure yapilandirmasini dondurur.
    Ornek: {'type': 'continuous', 'min': 4, 'max': 30, 'step': 1, 'default': 5}
    veya: {'type': 'discrete', 'options': [4, 6, 8], 'default': 4}
    """
    model_data = VIDEO_MODELS_CONFIG.get(model_key, {})
    cfg = model_data.get("duration_config")
    if cfg:
        return cfg
    durations = model_data.get("supported_durations", [5])
    return {
        "type": "discrete",
        "options": durations,
        "default": durations[0] if durations else 5
    }


def validate_model_duration(model_key: str, duration: int) -> bool:
    """
    Verilen surenin model tarafindan desteklenip desteklenmedigini dogrular.
    """
    cfg = get_model_duration_config(model_key)
    if cfg.get("type") == "continuous":
        step = cfg.get("step", 1)
        min_v = cfg.get("min", 1)
        max_v = cfg.get("max", 30)
        return min_v <= duration <= max_v and ((duration - min_v) % step == 0)
    else:
        return duration in cfg.get("options", [])


def resolve_image_action_and_credit(
    model_key: str,
    resolution: str = "1K",
    has_reference: bool = False,
    batch_size: int = 1
):
    """
    Verilen resim modeli, cozunurluk, referans durumu ve batch size'a gore (feature_id, action_id, unit_credit, total_credit) dondurur.
    """
    model_data = IMAGE_MODELS_CONFIG.get(model_key, IMAGE_MODELS_CONFIG["gpt_image_2_5_sunburst"])
    is_style_ref = model_data.get("effect_type") == "TtiStyleRef"
    if is_style_ref:
        feature_id = "TtiStyleRef"
        action_id = f"gen_{batch_size}_img"
        unit_credit = 1
        total_credit = 1 * batch_size
    else:
        feature_id = "TextToImage"
        mode_key = "enable" if (has_reference and model_data.get("ref_img_limit", 0) > 0) else "none"
        prefix = model_data.get("actionId_prefix", "genimage")
        res_suffix = resolution.lower() if ("alibaba_qwen" in prefix or "nanobanana2.1" in prefix or "kling_o1" in prefix) else resolution
        action_id = f"{prefix}_{mode_key}_{res_suffix}"

        if action_id in CYBERLINK_ACTION_CREDITS:
            unit_credit = CYBERLINK_ACTION_CREDITS[action_id]
        else:
            credits_dict = model_data.get("credits", {}).get(mode_key, {})
            unit_credit = credits_dict.get(resolution, 2)
        total_credit = unit_credit * batch_size

    return feature_id, action_id, unit_credit, total_credit




def generate_ai_image_service(
    member_token: str,
    user_prompt: str = "a majestic fantasy landscape, digital art, highly detailed 8k",
    image_paths: list = None,
    model_key: str = "NANO_BANANA",
    style_id: str = None,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    batch_size: str = "1",
    output_format: str = "jpeg",
    filename_prefix: str = "",
    task_id: str = None,
):
    model_key = IMAGE_MODEL_MAPPING.get(model_key, model_key)
    if model_key not in IMAGE_MODELS_CONFIG:
        raise ValueError(f"Unsupported model: {model_key}")

    model_data = IMAGE_MODELS_CONFIG[model_key]
    if not style_id:
        style_id = model_data.get("default_style", "Style_Default")

    if len(user_prompt) > model_data["promptLength"]:
        user_prompt = user_prompt[:model_data["promptLength"]]

    has_reference = False
    ref_limit = model_data.get("ref_img_limit", 0)
    if image_paths and len(image_paths) > 0:
        if ref_limit == 0:
            raise ValueError("Reference image not supported by model.")
        if len(image_paths) > ref_limit:
            image_paths = image_paths[:ref_limit]
        has_reference = True

    is_style_ref = model_data.get("effect_type") == "TtiStyleRef"
    try:
        b_size = int(batch_size)
    except ValueError:
        b_size = 1

    feature_id_val, action_id_val, unit_credit_cost, total_credit_cost = resolve_image_action_and_credit(
        model_key=model_key,
        resolution=resolution,
        has_reference=has_reference,
        batch_size=b_size
    )
    sync_feature_credit(feature_id=feature_id_val, action_id=action_id_val, credit=total_credit_cost)
    rsa_pub_key = get_myedit_rsa_public_key()
    sub_token = get_subscription_token(member_token)

    loaded_images_bytes = []
    if has_reference and image_paths:
        for p in image_paths:
            with open(p, "rb") as f:
                loaded_images_bytes.append(f.read())

    version_val = "4" if ("flux" in model_key or model_key == "z_image") else "5"
    if is_style_ref and not loaded_images_bytes:
        from PIL import Image
        import io
        img = Image.new('RGB', (512, 512), color=(120, 160, 220))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        loaded_images_bytes.append(buf.getvalue())

    aes_key = AESGCM.generate_key(bit_length=256)
    ts_ms = int(time.time() * 1000)
    key_param = rsa_encrypt_aes_key(rsa_pub_key, aes_key)
    receipt_json = json.dumps({"product": "myedit", "version": "3.9.0", "versiontype": "3.9.0", "platform": "web"}, separators=(',', ':'))
    receipt_param = encrypt_myedit_aes_gcm(aes_key, receipt_json, ts_ms, 0)
    enc_member_token = encrypt_myedit_aes_gcm(aes_key, member_token, ts_ms, 0)

    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Origin": "https://myedit.online",
        "Referer": "https://myedit.online/en/photo-editor/ai-image-generator/edit",
    }
    
    form_data_init = {
        "receipt": receipt_param,
        "member_token": enc_member_token,
        "key": key_param,
        "timestamp": str(ts_ms),
    }

    if loaded_images_bytes:
        if is_style_ref:
            filename_val = "TEXT_TO_IMAGE_STYLE_source"
        else:
            if image_paths and len(image_paths) > 0:
                ext = os.path.splitext(image_paths[0])[1].replace(".", "").lower() or "jpg"
                if ext == "jpeg":
                    ext = "jpg"
            else:
                ext = "jpg"
            filename_val = f"TEXT_TO_IMAGE_source_0.{ext}"
        form_data_init["filename"] = filename_val
        form_data_init["filesize"] = str(len(loaded_images_bytes[0]))

    resp_init = requests.post(MYEDIT_TTI_URL, data=form_data_init, headers=headers, timeout=30)
    if resp_init.status_code == 403 or "Fail to verify credit" in resp_init.text or ("Forbidden" in resp_init.text and "credit" in resp_init.text.lower()):
        raise CreditExhaustedError(f"Credit verification failed: {resp_init.text}")
    if resp_init.status_code == 401:
        raise AuthExpiredError(f"Auth token expired: {resp_init.text}")
    resp_init.raise_for_status()
    init_json = resp_init.json()
    
    s_id_str = str(init_json["s_id"])
    s_id_int = int(s_id_str)
    s_token_b64 = init_json["s_token"]
    raw_session_token = decrypt_myedit_aes_gcm(aes_key, s_token_b64, ts_ms, 0)

    uploaded_sources_list = []
    uploaded_reference_urls = []
    if loaded_images_bytes:
        put_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Content-Type": "image/jpeg",
            "Origin": "https://myedit.online",
            "Referer": "https://myedit.online/",
        }

        for idx, img_bytes in enumerate(loaded_images_bytes):
            if is_style_ref:
                fname = "TEXT_TO_IMAGE_STYLE_source"
            else:
                if image_paths and idx < len(image_paths):
                    ext = os.path.splitext(image_paths[idx])[1].replace(".", "").lower() or "jpg"
                    if ext == "jpeg":
                        ext = "jpg"
                else:
                    ext = "jpg"
                fname = f"TEXT_TO_IMAGE_source_{idx}.{ext}"
            fsize = str(len(img_bytes))

            req_ts_ms = int(time.time() * 1000)
            enc_token_hex = encrypt_myedit_aes_gcm_hex(aes_key, raw_session_token, req_ts_ms, s_id_int)
            get_link_url = f"{MYEDIT_TTI_URL}/{enc_token_hex}-{s_id_str}-{req_ts_ms}"

            resp_link = requests.post(get_link_url, data={"filename": fname, "filesize": fsize}, headers=headers, timeout=30)
            resp_link.raise_for_status()
            storage_url = resp_link.json()["storage"]
            
            clean_url = storage_url.split("?")[0]
            uploaded_reference_urls.append(clean_url)

            resp_upload = requests.put(storage_url, data=img_bytes, headers=put_headers, timeout=30)
            resp_upload.raise_for_status()
            uploaded_sources_list.append(idx + 1)

        if task_id and uploaded_reference_urls:
            db.update_task_reference_urls(task_id, [make_proxy_url(u) for u in uploaded_reference_urls])

    sources_str = json.dumps(uploaded_sources_list)

    req_ts_ms = int(time.time() * 1000)
    enc_token_hex = encrypt_myedit_aes_gcm_hex(aes_key, raw_session_token, req_ts_ms, s_id_int)
    apply_url = f"{MYEDIT_TTI_URL}/{enc_token_hex}-{s_id_str}-{req_ts_ms}"

    alias_str = time.strftime("%y%m%d_%H%M")
    apply_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Authorization": f"Bearer {member_token}",
        "x-subscription-token": f"Bearer {sub_token}",
        "Origin": "https://myedit.online",
        "Referer": "https://myedit.online/en/photo-editor/ai-image-generator/edit",
    }
    
    consumption_data = {
        "member_token": member_token,
        "cl_sid": SID_AOL_POL,
        "feature_id": feature_id_val,
        "action_id": action_id_val,
        "unit": 1 if is_style_ref else int(batch_size),
        "total_credit": total_credit_cost
    }
    consumption_param = encrypt_myedit_aes_gcm(
        aes_key,
        json.dumps(consumption_data, separators=(',', ':')),
        req_ts_ms,
        s_id_int
    )

    if is_style_ref:
        form_data_apply = {
            "source": str(uploaded_sources_list[0]) if uploaded_sources_list else "1",
            "aspect_ratio": aspect_ratio,
            "user_prompt": user_prompt,
            "need_translate": "true",
            "need_bad_word_check": "false",
            "batch_size": str(batch_size),
            "consumption": consumption_param,
            "cloud_sync": "true",
            "alias": alias_str,
            "effect": "TtiStyleRef",
        }
    else:
        form_data_apply = {
            "style_id": style_id,
            "style_prompt": "",
            "version": version_val,
            "aspect_ratio": aspect_ratio,
            "output_format": output_format,
            "user_prompt": user_prompt,
            "batch_size": str(batch_size),
            "consumption": consumption_param,
            "cloud_sync": "true",
            "alias": alias_str,
            "effect": "TextToImage",
        }

        if "flux" not in model_key:
            form_data_apply["resolution"] = resolution
        if has_reference:
            form_data_apply["sources"] = sources_str
        if "flux" in model_key:
            form_data_apply["need_translate"] = "true"
            form_data_apply["need_bad_word_check"] = "false"

    files_apply = {k: (None, str(v)) for k, v in form_data_apply.items()}

    resp_apply = requests.patch(apply_url, files=files_apply, headers=apply_headers, timeout=30)
    if task_id:
        db.add_task_log(task_id, str(resp_apply.status_code))
    if resp_apply.status_code == 403 or "Fail to verify credit" in resp_apply.text or ("Forbidden" in resp_apply.text and "credit" in resp_apply.text.lower()):
        raise CreditExhaustedError(f"Credit verification failed: {resp_apply.text}")
    if resp_apply.status_code == 401:
        raise AuthExpiredError(f"Auth token expired: {resp_apply.text}")
    resp_apply.raise_for_status()

    apply_json = resp_apply.json()
    cl_task_id = apply_json.get("task_id")
    polling = apply_json.get("polling", {})
    delay = polling.get("delay", 5)

    max_attempts = 360
    decrypted_files = []
    for i in range(max_attempts):
        time.sleep(delay)
        req_ts_ms = int(time.time() * 1000)
        enc_token_hex = encrypt_myedit_aes_gcm_hex(aes_key, raw_session_token, req_ts_ms, s_id_int)
        poll_url = f"{MYEDIT_TTI_URL}/{enc_token_hex}-{s_id_str}-{req_ts_ms}/{cl_task_id}"

        resp_poll = requests.get(poll_url, headers=headers, timeout=30)
        resp_poll.raise_for_status()
        poll_json = resp_poll.json()
        status = poll_json.get("status")

        if status == "Done":
            files = poll_json.get("files", [])
            s3_files = []
            dec_metadata = None
            for idx, f in enumerate(files):
                furl = f.get("url", "")
                task_info = f.get("task", {})
                # Her zaman ilk oturum anahtari (p_key) kullanilmalidir.
                enc_key = init_json.get("p_key")
                enc_iv = init_json.get("p_iv")

                if furl:
                    s3_files.append(furl)
                    if enc_key and enc_iv and not dec_metadata:
                        dec_metadata = {
                            "aes_key": aes_key.hex(),
                            "enc_key": enc_key,
                            "enc_iv": enc_iv,
                            "ts_ms": ts_ms
                        }
            return {
                "status": "Done",
                "files": s3_files,
                "reference_urls": uploaded_reference_urls,
                "decryption_metadata": dec_metadata
            }

        if status in ("Error", "Failed"):
            poll_err_str = json.dumps(poll_json)
            if "credit" in poll_err_str.lower() or "Forbidden" in poll_err_str:
                raise CreditExhaustedError(f"Task failed due to credit limit: {poll_err_str}")
            return {"status": "Failed", "error": poll_json, "reference_urls": uploaded_reference_urls}

    return {"status": "Timeout", "reference_urls": uploaded_reference_urls}


def generate_ai_video_service(
    member_token: str,
    user_prompt: str = "a cute astronaut cat floating in space station, cinematic lighting",
    model_key: str = "sora_2_std",
    aspect_ratio: str = "16:9",
    resolution: str = "720p",
    processing_duration: int = 8,
    sound: str = "none",
    effect_mode: str = "TextToVideo",
    source_image_path: str = None,
    last_image_path: str = None,
    ref_images: list = None,
    ref_videos: list = None,
    frame_mode: str = "single",
    filename_prefix: str = "",
    task_id: str = None,
):
    actual_model_key = VIDEO_MODEL_MAPPING.get(model_key, model_key)
    model_data = VIDEO_MODELS_CONFIG.get(actual_model_key, VIDEO_MODELS_CONFIG.get("sora_2_std"))
    if isinstance(model_data["model"], dict):
        model_name_str = model_data["model"].get(effect_mode, list(model_data["model"].values())[0])
    else:
        model_name_str = model_data["model"]
    vendor_str = model_data["vendor"]

    if effect_mode == "ReferenceToVideo":
        limit = model_data.get("reference_media_limit", {})
        supported_types = limit.get("supported_types", ["image"])
        num_images = len(ref_images) if ref_images else 0
        num_videos = len(ref_videos) if ref_videos else 0
        
        if num_images > 0 and "image" not in supported_types:
            raise ValueError("Reference images not supported.")
        if num_videos > 0 and "video" not in supported_types:
            raise ValueError("Reference videos not supported.")
            
        max_images = limit.get("max_images")
        max_videos = limit.get("max_videos")
        max_total = limit.get("max_total", (max_images or 0) + (max_videos or 0))
        
        if max_images and num_images > max_images:
            raise ValueError("Image count exceeds limit.")
        if max_videos and num_videos > max_videos:
            raise ValueError("Video count exceeds limit.")
        if max_total and (num_images + num_videos) > max_total:
            raise ValueError("Total references exceed limit.")

    SORA_RESOLUTION_MAP = {
        ("720p", "16:9"): "1280:720",
        ("720p", "9:16"): "720:1280",
        ("1080p", "16:9"): "1792:1024",
        ("1080p", "9:16"): "1024:1792",
    }

    if effect_mode == "ImageToVideo" and last_image_path:
        frame_mode = "startend"

    prepared_media = []
    if effect_mode == "ImageToVideo" and source_image_path and os.path.exists(source_image_path):
        target_w, target_h = None, None
        if vendor_str == "OpenAI":
            sora_res = SORA_RESOLUTION_MAP.get((resolution, aspect_ratio), "1280:720")
            target_w, target_h = map(int, sora_res.split(":"))
        else:
            try:
                ar_w, ar_h = map(int, aspect_ratio.split(":"))
            except Exception:
                ar_w, ar_h = 16, 9
            
            h_val = 720
            if resolution == "480p": h_val = 480
            elif resolution == "540p": h_val = 540
            elif resolution == "768p": h_val = 768
            elif resolution == "1080p": h_val = 1080
            elif resolution == "2k": h_val = 1440
            elif resolution == "4k": h_val = 2160
            
            if ar_w == 16 and ar_h == 9:
                target_w, target_h = int(h_val * 16 / 9), h_val
            elif ar_w == 9 and ar_h == 16:
                target_w, target_h = h_val, int(h_val * 16 / 9)
            elif ar_w == 1 and ar_h == 1:
                target_w, target_h = (1024, 1024) if h_val >= 720 else (720, 720)
            else:
                target_w, target_h = int(h_val * ar_w / ar_h), h_val
        
        temp1 = prepare_image_for_vgen(source_image_path, aspect_ratio, target_w, target_h, suffix="_first")
        prepared_media.append({
            "path": temp1,
            "tag": "first_frame",
            "type": "image",
            "is_temp": temp1 != source_image_path
        })
        
        if frame_mode == "startend" and last_image_path and os.path.exists(last_image_path):
            temp2 = prepare_image_for_vgen(last_image_path, aspect_ratio, target_w, target_h, suffix="_end")
            prepared_media.append({
                "path": temp2,
                "tag": "end_frame",
                "type": "image",
                "is_temp": temp2 != last_image_path
            })
            
    elif effect_mode == "ReferenceToVideo":
        if ref_images:
            for idx, item in enumerate(ref_images):
                img_path = item["path"] if isinstance(item, dict) else item
                if os.path.exists(img_path):
                    prepared_media.append({"path": img_path, "tag": f"@image{idx+1}", "type": "image", "is_temp": False})
        if ref_videos:
            for idx, item in enumerate(ref_videos):
                vid_path = item["path"] if isinstance(item, dict) else item
                if os.path.exists(vid_path):
                    prepared_media.append({"path": vid_path, "tag": f"@video{idx+1}", "type": "video", "is_temp": False})

    def cleanup_temp_images():
        for media in prepared_media:
            if media["is_temp"] and os.path.exists(media["path"]):
                try:
                    os.remove(media["path"])
                except Exception:
                    pass

    action_id_str, credit_cost = resolve_video_action_and_credit(
        model_key=actual_model_key,
        effect_mode=effect_mode,
        resolution=resolution,
        sound=sound,
        frame_mode=frame_mode
    )

    get_member_remaining_credits(member_token)
    sync_feature_credit(feature_id=effect_mode, action_id=action_id_str, credit=credit_cost * processing_duration)

    rsa_pub_key = get_myedit_rsa_public_key()
    sub_token = get_subscription_token(member_token)
    referer_url = "https://myedit.online/en/video-editor/image-to-video/edit" if effect_mode == "ImageToVideo" else "https://myedit.online/en/video-editor/text-to-video/edit"

    aes_key = AESGCM.generate_key(bit_length=256)
    ts_ms = int(time.time() * 1000)
    key_param = rsa_encrypt_aes_key(rsa_pub_key, aes_key)

    receipt_obj = {
        "product": "MyEdit",
        "version": "3.9.0",
        "versiontype": "3.9.0",
        "platform": "web",
        "consumption": {
            "member_token": member_token,
            "cl_sid": SID_AOL_POL,
            "feature_id": effect_mode,
            "action_id": action_id_str,
            "unit": processing_duration,
            "total_credit": credit_cost * processing_duration,
        },
    }
    receipt_json = json.dumps(receipt_obj, separators=(",", ":"))
    receipt_param = encrypt_myedit_aes_gcm(aes_key, receipt_json, ts_ms, 0)

    headers_init = {
        "User-Agent": HEADERS["User-Agent"],
        "Origin": "https://myedit.online",
        "Referer": referer_url,
    }

    files_init = {
        "key": (None, key_param),
        "timestamp": (None, str(ts_ms)),
        "receipt": (None, receipt_param),
    }

    if prepared_media:
        sources_list = []
        for i, item in enumerate(prepared_media):
            file_size = os.path.getsize(item["path"])
            filename = os.path.basename(item["path"])
            sources_list.append({"filename": filename, "filesize": file_size})
        files_init["sources"] = (None, json.dumps(sources_list, separators=(",", ":")))

    resp_init = requests.post(MYEDIT_VGEN_URL, files=files_init, headers=headers_init, timeout=30)
    if resp_init.status_code == 403 or "Fail to verify credit" in resp_init.text or ("Forbidden" in resp_init.text and "credit" in resp_init.text.lower()):
        raise CreditExhaustedError(f"Credit verification failed: {resp_init.text}")
    if resp_init.status_code == 401:
        raise AuthExpiredError(f"Auth token expired: {resp_init.text}")
    resp_init.raise_for_status()
    init_json = resp_init.json()
    
    s_id_str = str(init_json["s_id"])
    s_id_int = int(s_id_str)
    s_token_b64 = init_json["s_token"]
    raw_session_token = decrypt_myedit_aes_gcm(aes_key, s_token_b64, ts_ms, 0)

    uploaded_reference_urls = []
    if prepared_media:
        media_info_list = init_json.get("media_info", [])
        for i, item in enumerate(prepared_media):
            if i < len(media_info_list) and "url" in media_info_list[i]:
                upload_url = media_info_list[i]["url"]
                
                clean_url = upload_url.split("?")[0]
                uploaded_reference_urls.append(clean_url)

                with open(item["path"], 'rb') as f:
                    file_data = f.read()
                content_type = 'video/mp4' if item["type"] == "video" else 'image/jpeg'
                resp_upload = requests.put(upload_url, data=file_data, headers={'Content-Type': content_type})

        if task_id and uploaded_reference_urls:
            db.update_task_reference_urls(task_id, [make_proxy_url(u) for u in uploaded_reference_urls])

    req_ts_ms = int(time.time() * 1000)
    enc_token_hex = encrypt_myedit_aes_gcm_hex(aes_key, raw_session_token, req_ts_ms, s_id_int)
    apply_url = f"{MYEDIT_VGEN_URL}/{enc_token_hex}-{s_id_str}-{req_ts_ms}"

    alias_str = time.strftime("%y%m%d_%H%M")
    apply_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Authorization": f"Bearer {member_token}",
        "x-subscription-token": f"Bearer {sub_token}",
        "Origin": "https://myedit.online",
        "Referer": referer_url,
    }

    sound_form_val = "vendor" if sound in ["vendor", "auto", "on", "On"] else "none"
    form_data_apply = {
        "vendor": vendor_str,
        "processing_duration": str(processing_duration),
        "user_prompt": user_prompt,
        "need_bad_word_check": "false",
        "sound": sound_form_val,
        "create_thumbnail": "true",
        "cloud_sync": "true",
        "alias": alias_str,
        "model": model_name_str,
        "is_custom": "true",
        "is_fixed_model": "true",
        "effect": effect_mode,
    }

    model_mode = model_data.get("mode")
    if not model_mode:
        model_mode = "pro" if resolution in ["1080p", "4k"] else "std"

    if prepared_media:
        media_info_list = init_json.get("media_info", [])
        media_ids = [m["id"] for m in media_info_list if "id" in m]
        first_frame_id = media_ids[0] if len(media_ids) > 0 else 1
        end_frame_id = media_ids[1] if len(media_ids) > 1 else None

        if effect_mode == "ImageToVideo":
            img_w, img_h = get_image_dimensions(prepared_media[0]["path"])
            image_file_size = os.path.getsize(prepared_media[0]["path"])

            if vendor_str in ["Alibaba", "Pixverse", "BytePlus", "Flux", "Hailuo"]:
                form_data_apply["width"] = str(img_w)
                form_data_apply["height"] = str(img_h)
                if vendor_str in ["Alibaba", "Hailuo"]:
                    form_data_apply["aspect_ratio"] = aspect_ratio
                    form_data_apply["resolution"] = resolution.upper()
                    if model_mode:
                        form_data_apply["mode"] = model_mode
                elif vendor_str == "BytePlus" and "2.5" in str(model_name_str):
                    form_data_apply["aspect_ratio"] = "adaptive"
                    form_data_apply["resolution"] = resolution
                    if model_mode:
                        form_data_apply["mode"] = model_mode
                else:
                    form_data_apply["mode"] = model_mode
                
                if end_frame_id is not None:
                    form_data_apply["sources"] = json.dumps([first_frame_id, end_frame_id])
                    image_list_obj = [
                        {"media_id": first_frame_id, "filesize": image_file_size, "width": img_w, "height": img_h, "type": "first_frame"},
                        {"media_id": end_frame_id, "filesize": os.path.getsize(prepared_media[1]["path"]), "width": img_w, "height": img_h, "type": "end_frame"}
                    ]
                else:
                    form_data_apply["sources"] = json.dumps([first_frame_id])
                    image_list_obj = [
                        {"media_id": first_frame_id, "filesize": image_file_size, "width": img_w, "height": img_h, "type": "first_frame"}
                    ]
                form_data_apply["image_list"] = json.dumps(image_list_obj, separators=(",", ":"))

            elif vendor_str == "OpenAI":
                sora_res = SORA_RESOLUTION_MAP.get((resolution, aspect_ratio), "1280:720")
                target_w, target_h = sora_res.split(":")
                form_data_apply["width"] = target_w
                form_data_apply["height"] = target_h
                form_data_apply["resolution"] = sora_res
                form_data_apply["sources"] = json.dumps([first_frame_id])
            else:
                form_data_apply["width"] = str(img_w)
                form_data_apply["height"] = str(img_h)
                form_data_apply["mode"] = model_mode
                
                if end_frame_id is not None:
                    form_data_apply["sources"] = json.dumps([first_frame_id, -1, end_frame_id])
                    last_image_file_size = os.path.getsize(prepared_media[1]["path"])
                    last_image_obj = {"media_id": end_frame_id, "filesize": last_image_file_size, "width": img_w, "height": img_h}
                    form_data_apply["last_image"] = json.dumps(last_image_obj, separators=(",", ":"))
                else:
                    form_data_apply["sources"] = json.dumps([first_frame_id])
                    
        elif effect_mode == "ReferenceToVideo":
            form_data_apply["sources"] = json.dumps(media_ids)
            form_data_apply["effect"] = "RefToVideo"
            image_list_obj = []
            video_list_obj = []
            for j, item in enumerate(prepared_media):
                if item["type"] == "image":
                    w_j, h_j = get_image_dimensions(item["path"])
                    size_j = os.path.getsize(item["path"])
                    image_list_obj.append({"media_id": media_ids[j], "filesize": size_j, "width": w_j, "height": h_j, "tag": item["tag"]})
                elif item["type"] == "video":
                    size_j = os.path.getsize(item["path"])
                    video_list_obj.append({"media_id": media_ids[j], "tag": item["tag"], "filesize": size_j})
            form_data_apply["image_list"] = json.dumps(image_list_obj, separators=(",", ":"))
            form_data_apply["video_list"] = json.dumps(video_list_obj, separators=(",", ":"))
            form_data_apply["audio_spec"] = json.dumps({"mode": "native"}, separators=(",", ":"))
            form_data_apply["aspect_ratio"] = aspect_ratio
            form_data_apply["resolution"] = resolution
            if model_mode:
                form_data_apply["mode"] = model_mode
    else:
        form_data_apply["aspect_ratio"] = aspect_ratio
        form_data_apply["resolution"] = resolution
        if model_mode:
            form_data_apply["mode"] = model_mode

    files_apply = {k: (None, str(v)) for k, v in form_data_apply.items()}
    resp_apply = requests.patch(apply_url, files=files_apply, headers=apply_headers, timeout=60)
    if task_id:
        db.add_task_log(task_id, str(resp_apply.status_code))
    if resp_apply.status_code == 403 or "Fail to verify credit" in resp_apply.text or ("Forbidden" in resp_apply.text and "credit" in resp_apply.text.lower()):
        raise CreditExhaustedError(f"Credit verification failed: {resp_apply.text}")
    if resp_apply.status_code == 401:
        raise AuthExpiredError(f"Auth token expired: {resp_apply.text}")
    resp_apply.raise_for_status()

    apply_json = resp_apply.json()
    cl_task_id = apply_json.get("task_id")
    polling = apply_json.get("polling", {})
    delay = polling.get("delay", 5)

    max_attempts = 360
    decrypted_files = []
    for i in range(max_attempts):
        time.sleep(delay)
        req_ts_ms = int(time.time() * 1000)
        enc_token_hex = encrypt_myedit_aes_gcm_hex(aes_key, raw_session_token, req_ts_ms, s_id_int)
        poll_url = f"{MYEDIT_VGEN_URL}/{enc_token_hex}-{s_id_str}-{req_ts_ms}/{cl_task_id}"

        resp_poll = requests.get(poll_url, headers=headers_init, timeout=30)
        resp_poll.raise_for_status()
        poll_json = resp_poll.json()
        status = poll_json.get("status")

        if status == "Done":
            files = poll_json.get("files", [])
            s3_files = []
            dec_metadata = None
            for idx, f in enumerate(files):
                furl = f.get("url", "")
                task_info = f.get("task", {})
                # Her zaman ilk oturum anahtari (p_key) kullanilmalidir.
                enc_key = init_json.get("p_key")
                enc_iv = init_json.get("p_iv")

                if furl:
                    # If this is a thumbnail URL returned instead of the video, fetch the real mp4 URL
                    if "thumbnail" in furl.lower() and idx == 0:
                        try:
                            import re
                            match = re.search(r'/Credit/(\d+)/', furl)
                            if match:
                                consume_task_id = match.group(1)
                                req_ts_ms_consume = int(time.time() * 1000)
                                enc_token_hex = encrypt_myedit_aes_gcm_hex(aes_key, raw_session_token, req_ts_ms_consume, s_id_int)
                                consume_url = f"https://myedit.online/info/consume/{enc_token_hex}-{s_id_str}-{req_ts_ms_consume}/tasks/files"
                                
                                files_form = {
                                    "consume_task_id": (None, str(consume_task_id)),
                                    "sync_status": (None, "1,2"),
                                    "sort_by": (None, "created_time asc"),
                                }
                                
                                resp_consume = requests.post(consume_url, files=files_form, headers=headers_init, timeout=30)
                                resp_consume.raise_for_status()
                                consume_json = resp_consume.json()
                                
                                result_files = consume_json.get("files", [])
                                if result_files:
                                    # Find the mp4 file in the consume files list
                                    mp4_file = None
                                    for rf in result_files:
                                        rf_url = rf.get("url", "")
                                        rf_name = rf.get("name", "")
                                        if rf_name.lower().endswith(".mp4") or (".mp4" in rf_url.lower() and "thumbnail" not in rf_url.lower()):
                                            mp4_file = rf
                                            break
                                    
                                    if not mp4_file:
                                        mp4_file = result_files[0]
                                    
                                    furl = mp4_file.get("url", furl)
                                    rf_task = mp4_file.get("task", {})
                                    # Her zaman ilk oturum anahtari kullanilmaya devam edilmelidir.
                        except Exception as e:
                            print(f"[THUMBNAIL-FIX] Failed to fetch real video URL: {e}")

                    s3_files.append(furl)
                    if enc_key and enc_iv and not dec_metadata:
                        dec_metadata = {
                            "aes_key": aes_key.hex(),
                            "enc_key": enc_key,
                            "enc_iv": enc_iv,
                            "ts_ms": ts_ms
                        }
            cleanup_temp_images()
            return {
                "status": "Done",
                "files": s3_files,
                "reference_urls": uploaded_reference_urls,
                "decryption_metadata": dec_metadata
            }

        if status in ("Error", "Failed"):
            cleanup_temp_images()
            poll_err_str = json.dumps(poll_json)
            if "credit" in poll_err_str.lower() or "Forbidden" in poll_err_str:
                raise CreditExhaustedError(f"Task failed due to credit limit: {poll_err_str}")
            return {"status": "Failed", "error": poll_json, "reference_urls": uploaded_reference_urls}

    cleanup_temp_images()
    return {"status": "Timeout", "reference_urls": uploaded_reference_urls}

# ==============================================================================
# service.py ACCOUNT CACHE & REUSE SYSTEM
# ==============================================================================


ACTIVE_ACCOUNTS = {} # {api_key_id: {"email": email, "password": password, "member_token": token, "timestamp": time.time()}}
ACCOUNT_LOCK = threading.Lock()

def mark_account_exhausted(api_key_id, email):
    """Marks an account as used=1 (credits exhausted) in the database and removes it from active cache."""
    with ACCOUNT_LOCK:
        if api_key_id in ACTIVE_ACCOUNTS and ACTIVE_ACCOUNTS[api_key_id].get("email") == email:
            del ACTIVE_ACCOUNTS[api_key_id]
    try:
        if db.DB_TYPE == 'postgresql':
            db._execute_query('UPDATE accounts SET used = 1 WHERE api_key_id = %s AND email = %s', (api_key_id, email))
        else:
            db._execute_query('UPDATE accounts SET used = 1 WHERE api_key_id = ? AND email = ?', (api_key_id, email))
        print(f"[ACCOUNT] Account {email} marked as used=1 (credits exhausted).")
    except Exception as e:
        print(f"[ACCOUNT] Error marking account exhausted: {e}")

def create_myedit_account(api_key_id):
    """Creates a new MyEdit account dynamically on-the-fly.
    Uses TempMailClient for temp mail. Saves account to database with used=0.
    """
    try:
        temp_mail = TempMailClient()
        email = temp_mail.get_email()
        password = "CyberLink123!"

        # 1. Signup
        signup_res = signup(email, password)
        if signup_res.get("status") != "SUCCESS":
            print(f"[-] Signup failed: {signup_res}")
            return None, None

        # 2. Get activation link
        try:
            activation_url = temp_mail.wait_for_activation_link(timeout=60)
        except Exception as e:
            print(f"[-] Activation link not received: {e}")
            return None, None

        # 3. Activate
        if not activate_account(activation_url):
            print("[-] Activation not verified, trying login anyway...")

        # Wait for activation propagation
        time.sleep(3)

        # 4. Login
        login_res = login(email, password)
        if login_res.get("status") != "SUCCESS":
            print(f"[-] Login failed: {login_res}")
            return None, None

        info = login_res.get("info", {})
        member_token = info.get("memberToken")
        if not member_token:
            print("[-] Login failed, no memberToken.")
            return None, None
        
        # 5. Collect all daily and task bonuses (174 credits total)
        try:
            collect_all_bonuses(member_token)
        except Exception as e:
            print(f"[!] Bonus collection failed: {e}")

        # Add account to database (used = 0)
        db.add_account(api_key_id, email, password)
        print(f"[+] Successfully registered and saved MyEdit account: {email}")

        return member_token, email
    except Exception as e:
        print(f"[-] Account creation exception: {e}")
        return None, None

def create_myedit_account_wrapper(api_key_id):
    """Wrapper function matching naming structure."""
    return create_myedit_account(api_key_id)

def get_or_create_active_account(api_key_id, task_id=None, force_new=False):
    """Gets an active account from memory cache, existing DB account, or creates a new one.
    Ensures maximum speed by reusing the token until credits are exhausted.
    """
    # 1. Check memory cache if not force_new
    if not force_new:
        with ACCOUNT_LOCK:
            if api_key_id in ACTIVE_ACCOUNTS:
                acc = ACTIVE_ACCOUNTS[api_key_id]
                email = acc.get("email")
                member_token = acc.get("member_token")
                if member_token and email:
                    if task_id:
                        try:
                            if db.DB_TYPE == 'postgresql':
                                db._execute_query('UPDATE tasks SET account_email = %s WHERE task_id = %s', (email, task_id))
                            else:
                                db._execute_query('UPDATE tasks SET account_email = ? WHERE task_id = ?', (email, task_id))
                        except Exception:
                            pass
                    return member_token, acc

    # 2. Check if DB has the most recently created valid account (ORDER BY id DESC)
    if not force_new:
        try:
            query = 'SELECT email, password FROM accounts WHERE api_key_id = %s ORDER BY id DESC LIMIT 1' if db.DB_TYPE == 'postgresql' else 'SELECT email, password FROM accounts WHERE api_key_id = ? ORDER BY id DESC LIMIT 1'
            db_acc = db._execute_query(query, (api_key_id,), fetch_one=True)
            if db_acc and db_acc.get("email") and db_acc.get("password"):
                email = db_acc["email"]
                password = db_acc["password"]
                print(f"[ACCOUNT] Found latest account in DB: {email}. Attempting login...")
                login_res = login(email, password)
                if login_res.get("status") == "SUCCESS" and "info" in login_res:
                    member_token = login_res["info"].get("memberToken")
                    if member_token:
                        acc_data = {
                            "email": email,
                            "password": password,
                            "member_token": member_token,
                            "timestamp": time.time()
                        }
                        with ACCOUNT_LOCK:
                            ACTIVE_ACCOUNTS[api_key_id] = acc_data
                        if task_id:
                            try:
                                if db.DB_TYPE == 'postgresql':
                                    db._execute_query('UPDATE tasks SET account_email = %s WHERE task_id = %s', (email, task_id))
                                else:
                                    db._execute_query('UPDATE tasks SET account_email = ? WHERE task_id = ?', (email, task_id))
                            except Exception:
                                pass
                        return member_token, acc_data
                else:
                    print(f"[ACCOUNT] Login failed for DB account ({email}). Registering a fresh new account...")
        except Exception as e:
            print(f"[ACCOUNT] Error retrieving DB account: {e}")

    # 3. Create a fresh account via temp-mail
    for attempt in range(5):
        print(f"[ACCOUNT] Registering new account for api_key_id={api_key_id} (attempt {attempt+1}/5)...")
        member_token, email = create_myedit_account_wrapper(api_key_id)
        if member_token and email:
            password = "CyberLink123!"
            acc_data = {
                "email": email,
                "password": password,
                "member_token": member_token,
                "timestamp": time.time()
            }
            with ACCOUNT_LOCK:
                ACTIVE_ACCOUNTS[api_key_id] = acc_data
            if task_id:
                try:
                    if db.DB_TYPE == 'postgresql':
                        db._execute_query('UPDATE tasks SET account_email = %s WHERE task_id = %s', (email, task_id))
                    else:
                        db._execute_query('UPDATE tasks SET account_email = ? WHERE task_id = ?', (email, task_id))
                except Exception:
                    pass
            return member_token, acc_data
        time.sleep(2)

    return None, None

def deduct_api_key_quota(api_key_id, task_id=None, amount=1):
    """Deducts `amount` (default 1) accounts/quotas from the API key's available accounts upon successful task completion.
    Prioritizes accounts other than the currently active working account so the active account remains intact in DB.
    Even if the active account's DB row is consumed, its in-memory session (ACTIVE_ACCOUNTS) stays fully operational.
    """
    try:
        if amount is None or amount <= 0:
            amount = 1

        active_acc = ACTIVE_ACCOUNTS.get(api_key_id)
        active_email = active_acc.get("email") if active_acc else None

        conn = db.get_connection()
        cursor = conn.cursor()
        consumed_emails = []

        if db.DB_TYPE == 'postgresql':
            # 1. Önce aktif çalışan hesap DIŞINDAKİ boş hesapları seç
            if active_email:
                cursor.execute(
                    'SELECT email FROM accounts WHERE api_key_id = %s AND used = 0 AND email != %s LIMIT %s',
                    (api_key_id, active_email, amount)
                )
                rows = cursor.fetchall()
                for row in rows:
                    email_val = row['email'] if isinstance(row, dict) else row[0]
                    consumed_emails.append(email_val)
            
            # 2. Eğer daha fazla kota gerekiyorsa (aktif hesap dahil)
            remaining_needed = amount - len(consumed_emails)
            if remaining_needed > 0:
                cursor.execute(
                    'SELECT email FROM accounts WHERE api_key_id = %s AND used = 0 LIMIT %s',
                    (api_key_id, remaining_needed)
                )
                rows = cursor.fetchall()
                for row in rows:
                    email_val = row['email'] if isinstance(row, dict) else row[0]
                    if email_val not in consumed_emails:
                        consumed_emails.append(email_val)

            if consumed_emails:
                cursor.execute(
                    'UPDATE accounts SET used = 1 WHERE api_key_id = %s AND email = ANY(%s)',
                    (api_key_id, consumed_emails)
                )
                if task_id:
                    cursor.execute(
                        'UPDATE tasks SET account_email = %s WHERE task_id = %s',
                        (consumed_emails[0], task_id)
                    )
                conn.commit()
                print(f"[QUOTA] Successfully deducted {len(consumed_emails)} quota units (requested {amount}) for task {task_id}.")
        else:
            # SQLite versiyonu
            if active_email:
                cursor.execute(
                    'SELECT email FROM accounts WHERE api_key_id = ? AND used = 0 AND email != ? LIMIT ?',
                    (api_key_id, active_email, amount)
                )
                rows = cursor.fetchall()
                for row in rows:
                    email_val = row['email'] if isinstance(row, dict) else row[0]
                    consumed_emails.append(email_val)

            remaining_needed = amount - len(consumed_emails)
            if remaining_needed > 0:
                cursor.execute(
                    'SELECT email FROM accounts WHERE api_key_id = ? AND used = 0 LIMIT ?',
                    (api_key_id, remaining_needed)
                )
                rows = cursor.fetchall()
                for row in rows:
                    email_val = row['email'] if isinstance(row, dict) else row[0]
                    if email_val not in consumed_emails:
                        consumed_emails.append(email_val)

            if consumed_emails:
                placeholders = ','.join(['?'] * len(consumed_emails))
                cursor.execute(
                    f'UPDATE accounts SET used = 1 WHERE api_key_id = ? AND email IN ({placeholders})',
                    [api_key_id] + consumed_emails
                )
                if task_id:
                    cursor.execute(
                        'UPDATE tasks SET account_email = ? WHERE task_id = ?',
                        (consumed_emails[0], task_id)
                    )
                conn.commit()
                print(f"[QUOTA] Successfully deducted {len(consumed_emails)} quota units (requested {amount}) for task {task_id}.")
        conn.close()
        return consumed_emails
    except Exception as e:
        print(f"[QUOTA] Error deducting quota: {e}")
        return None

def login_with_retry_and_link(api_key_id, task_id=None):
    """Compatibility wrapper for obtaining active account."""
    return get_or_create_active_account(api_key_id, task_id)

def save_b64_to_temp_file(b64_data, suffix=".jpg"):
    """Saves base64 data to a local temporary file."""
    if "," in b64_data:
        b64_data = b64_data.split(",")[1]
    data = base64.b64decode(b64_data)
    os.makedirs("temp", exist_ok=True)
    temp_path = f"temp/ref_{int(time.time() * 1000)}_{random.randint(1000, 9999)}{suffix}"
    with open(temp_path, "wb") as f:
        f.write(data)
    return os.path.abspath(temp_path)

def process_image_task(task_id, params, api_key_id):
    temp_files = []
    try:
        db.update_task_status(task_id, 'running')

        prompt = params.get('prompt', '')
        raw_model = params.get('model', 'NANO_BANANA')
        model = IMAGE_MODEL_MAPPING.get(raw_model, raw_model)
        aspect_ratio = params.get('size', '1:1')
        resolution = params.get('resolution', '1K')
        batch_size = int(params.get('batch_size', 1))

        # Determine API quota to deduct for image model
        model_api_credit = 1
        for m in AVAILABLE_MODELS.get('image', []):
            if m.get('id') == raw_model or m.get('id') == model:
                model_api_credit = m.get('credit', 1)
                break
        total_quota_to_deduct = model_api_credit * batch_size

        # Handle reference images (Image-to-Image)
        reference_images = []
        images = params.get('reference_images', [])
        if images:
            for img_b64 in images:
                temp_path = save_b64_to_temp_file(img_b64)
                temp_files.append(temp_path)
                reference_images.append(temp_path)

        model_data = IMAGE_MODELS_CONFIG.get(model)
        if not model_data:
            db.update_task_status(task_id, 'failed')
            db.add_task_log(task_id, "400")
            return

        is_style_ref = model_data.get("effect_type") == "TtiStyleRef"
        feature_id = "TtiStyleRef" if is_style_ref else "TextToImage"

        max_account_retries = 3
        last_error = None
        result = None
        current_token = None

        for attempt in range(max_account_retries):
            force_new = (attempt > 0)
            member_token, account = get_or_create_active_account(api_key_id, task_id=task_id, force_new=force_new)
            if not member_token:
                db.update_task_status(task_id, 'failed')
                db.add_task_log(task_id, "503")
                return

            current_token = member_token
            try:
                credit_info = get_member_remaining_credits(member_token)
                total_credits = credit_info.get("total_remain", "?") if credit_info else "?"
                print(f"\n[RENDER LOG] [IMAGE TASK: {task_id}] -> Aktif Hesap: {account['email']} | Mevcut Kalan Kredi: {total_credits}")

                claim_task_bonus(member_token, feature_id)
                check_task_bonus(member_token, feature_id)

                token_data = json.dumps({
                    "member_token": member_token,
                    "reference_images": params.get('reference_images', []),
                    "reference_videos": params.get('reference_videos', []),
                    "start_frame": params.get('start_frame'),
                    "end_frame": params.get('end_frame')
                })
                db.update_task_token(task_id, token_data)

                result = generate_ai_image_service(
                    member_token=member_token,
                    user_prompt=prompt,
                    image_paths=reference_images if reference_images else None,
                    model_key=model,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    batch_size=str(batch_size),
                    filename_prefix=f"task_{task_id}",
                    task_id=task_id
                )
                break

            except CreditExhaustedError as e:
                print(f"[RETRY] Credit exhausted for account {account['email']} on image task {task_id}: {e}. Rotating to new account...")
                mark_account_exhausted(api_key_id, account['email'])
                last_error = e
                continue

            except (AuthExpiredError, requests.exceptions.HTTPError, Exception) as e:
                is_401 = isinstance(e, AuthExpiredError) or "401" in str(e) or (hasattr(e, 'response') and e.response is not None and e.response.status_code == 401)
                is_403 = isinstance(e, CreditExhaustedError) or "403" in str(e) or "Fail to verify credit" in str(e) or (hasattr(e, 'response') and e.response is not None and e.response.status_code == 403)
                if is_403:
                    print(f"[RETRY] 403 Credit exhausted for account {account['email']} on image task {task_id}: {e}. Rotating to new account...")
                    mark_account_exhausted(api_key_id, account['email'])
                    last_error = e
                    continue
                if is_401:
                    print(f"[RETRY] Auth token expired (401) for account {account['email']}. Re-logging in...")
                    login_res = login(account['email'], account['password'])
                    if login_res.get("status") == "SUCCESS" and "info" in login_res:
                        refreshed_token = login_res["info"].get("memberToken")
                        if refreshed_token:
                            with ACCOUNT_LOCK:
                                if api_key_id in ACTIVE_ACCOUNTS:
                                    ACTIVE_ACCOUNTS[api_key_id]["member_token"] = refreshed_token
                            last_error = e
                            continue
                    print(f"[RETRY] Re-login failed for account {account['email']}. Rotating to fresh account...")
                    mark_account_exhausted(api_key_id, account['email'])
                    last_error = e
                    continue
                # For any other unhandled exception in the loop
                last_error = e
                break

        if not result:
            db.update_task_status(task_id, 'failed')
            db.add_task_log(task_id, format_error_code(last_error))
            return

        if result.get("status") == "Done":
            completed_files = result.get("files", [])
            dec_metadata = result.get("decryption_metadata")
            token_data_dict = {
                "member_token": current_token,
                "reference_images": params.get('reference_images', []),
                "reference_videos": params.get('reference_videos', []),
                "start_frame": params.get('start_frame'),
                "end_frame": params.get('end_frame')
            }
            if dec_metadata:
                token_data_dict.update({
                    "dec_aes_key": dec_metadata.get("aes_key"),
                    "dec_enc_key": dec_metadata.get("enc_key"),
                    "dec_enc_iv": dec_metadata.get("enc_iv"),
                    "dec_ts_ms": dec_metadata.get("ts_ms")
                })
            db.update_task_token(task_id, json.dumps(token_data_dict))

            if completed_files:
                db.update_task_status(task_id, 'completed', make_proxy_url(completed_files[0]))
                deduct_api_key_quota(api_key_id, task_id, amount=total_quota_to_deduct)
                post_credits_info = get_member_remaining_credits(current_token)
                post_credits = post_credits_info.get("total_remain", "?") if post_credits_info else "?"
                print(f"[RENDER LOG] [IMAGE TASK: {task_id}] [TAMAMLANDI] -> Hesap: {account['email']} | Kalan Kredi: {post_credits}\n")
            else:
                db.update_task_status(task_id, 'failed')
                db.add_task_log(task_id, "500")
        elif result.get("status") == "Timeout":
            db.update_task_status(task_id, 'timeout')
            db.add_task_log(task_id, "504")
        else:
            db.update_task_status(task_id, 'failed')
            db.add_task_log(task_id, format_error_code(result.get('error')))

    except Exception as e:
        print(f"[ERROR] Image task {task_id} error: {e}")
        db.update_task_status(task_id, 'error')
        db.add_task_log(task_id, format_error_code(e))
    finally:
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

def process_video_task(task_id, params, api_key_id):
    temp_files = []
    try:
        db.update_task_status(task_id, 'running')

        prompt = params.get('prompt', '')
        has_start_frame = bool(params.get('start_frame'))
        default_model = 'sora_2_std' if has_start_frame else 'seedance_2_0_mini'
        raw_model = params.get('model') or default_model
        model = VIDEO_MODEL_MAPPING.get(raw_model, raw_model)
        aspect_ratio = params.get('size', '16:9')
        resolution = params.get('resolution', '720p')
        duration = int(params.get('duration', 8 if model == 'sora_2_std' else 10))
        sound = params.get('sound', 'vendor')

        # Determine API quota to deduct for video model
        model_api_credit = 1
        for m in AVAILABLE_MODELS.get('video', []):
            if m.get('id') == raw_model or m.get('id') == model:
                model_api_credit = m.get('credit', 1)
                break

        input_mode = "TextToVideo"
        source_image_path = None
        last_image_path = None
        ref_images = []
        ref_videos = []
        frame_mode = "single"

        # Handle start frame
        start_frame_b64 = params.get('start_frame')
        if start_frame_b64:
            input_mode = "ImageToVideo"
            temp_start = save_b64_to_temp_file(start_frame_b64)
            temp_files.append(temp_start)
            source_image_path = temp_start

        # Handle end frame
        end_frame_b64 = params.get('end_frame')
        if end_frame_b64 and start_frame_b64:
            frame_mode = "startend"
            temp_end = save_b64_to_temp_file(end_frame_b64)
            temp_files.append(temp_end)
            last_image_path = temp_end

        # Handle reference images / videos
        images = params.get('reference_images', [])
        videos = params.get('reference_videos', [])
        if images or videos:
            input_mode = "ReferenceToVideo"
            for img_b64 in images:
                temp_img = save_b64_to_temp_file(img_b64)
                temp_files.append(temp_img)
                ref_images.append(temp_img)
            for vid_b64 in videos:
                temp_vid = save_b64_to_temp_file(vid_b64, suffix=".mp4")
                temp_files.append(temp_vid)
                ref_videos.append(temp_vid)

        model_data = VIDEO_MODELS_CONFIG.get(model)
        if not model_data:
            db.update_task_status(task_id, 'failed')
            db.add_task_log(task_id, "400")
            return

        max_account_retries = 3
        last_error = None
        result = None
        current_token = None

        for attempt in range(max_account_retries):
            force_new = (attempt > 0)
            member_token, account = get_or_create_active_account(api_key_id, task_id=task_id, force_new=force_new)
            if not member_token:
                db.update_task_status(task_id, 'failed')
                db.add_task_log(task_id, "503")
                return

            current_token = member_token
            try:
                credit_info = get_member_remaining_credits(member_token)
                total_credits = credit_info.get("total_remain", "?") if credit_info else "?"
                print(f"\n[RENDER LOG] [VIDEO TASK: {task_id}] -> Aktif Hesap: {account['email']} | Mevcut Kalan Kredi: {total_credits}")

                claim_task_bonus(member_token, feature_id=input_mode)
                check_task_bonus(member_token, feature_id=input_mode)

                token_data = json.dumps({
                    "member_token": member_token,
                    "reference_images": params.get('reference_images', []),
                    "reference_videos": params.get('reference_videos', []),
                    "start_frame": params.get('start_frame'),
                    "end_frame": params.get('end_frame')
                })
                db.update_task_token(task_id, token_data)

                # If Sora 2 is invoked without a start frame, auto-generate initial frame from prompt
                current_source_image_path = source_image_path
                current_input_mode = input_mode
                if model == "sora_2_std" and current_input_mode == "TextToVideo" and not current_source_image_path:
                    try:
                        print(f"[SORA-2] Auto-generating initial frame for Text-to-Video task {task_id}...")
                        t2i_res = generate_ai_image_service(
                            member_token=member_token,
                            user_prompt=prompt,
                            model_key="NANO_BANANA_2",
                            aspect_ratio=aspect_ratio,
                            resolution="1K",
                            batch_size="1",
                            task_id=task_id
                        )
                        if t2i_res and t2i_res.get("status") == "Done" and t2i_res.get("files"):
                            img_url = t2i_res["files"][0]
                            img_resp = requests.get(img_url, timeout=30)
                            if img_resp.status_code == 200:
                                temp_auto_img = os.path.join(tempfile.gettempdir(), f"sora_auto_{task_id}.jpg")
                                with open(temp_auto_img, "wb") as f:
                                    f.write(img_resp.content)
                                temp_files.append(temp_auto_img)
                                current_source_image_path = temp_auto_img
                                current_input_mode = "ImageToVideo"
                    except Exception as ex:
                        print(f"[SORA-2] Auto-frame generation error: {ex}")

                result = generate_ai_video_service(
                    member_token=member_token,
                    user_prompt=prompt,
                    model_key=model,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    processing_duration=duration,
                    sound=sound,
                    effect_mode=current_input_mode,
                    source_image_path=current_source_image_path,
                    last_image_path=last_image_path,
                    ref_images=ref_images if ref_images else None,
                    ref_videos=ref_videos if ref_videos else None,
                    frame_mode=frame_mode,
                    filename_prefix=f"task_{task_id}",
                    task_id=task_id
                )
                break

            except CreditExhaustedError as e:
                print(f"[RETRY] Credit exhausted for account {account['email']} on video task {task_id}: {e}. Rotating to new account...")
                mark_account_exhausted(api_key_id, account['email'])
                last_error = e
                continue

            except (AuthExpiredError, requests.exceptions.HTTPError, Exception) as e:
                is_401 = isinstance(e, AuthExpiredError) or "401" in str(e) or (hasattr(e, 'response') and e.response is not None and e.response.status_code == 401)
                is_403 = isinstance(e, CreditExhaustedError) or "403" in str(e) or "Fail to verify credit" in str(e) or (hasattr(e, 'response') and e.response is not None and e.response.status_code == 403)
                if is_403:
                    print(f"[RETRY] 403 Credit exhausted for account {account['email']} on video task {task_id}: {e}. Rotating to new account...")
                    mark_account_exhausted(api_key_id, account['email'])
                    last_error = e
                    continue
                if is_401:
                    print(f"[RETRY] Auth token expired (401) for account {account['email']}. Re-logging in...")
                    login_res = login(account['email'], account['password'])
                    if login_res.get("status") == "SUCCESS" and "info" in login_res:
                        refreshed_token = login_res["info"].get("memberToken")
                        if refreshed_token:
                            with ACCOUNT_LOCK:
                                if api_key_id in ACTIVE_ACCOUNTS:
                                    ACTIVE_ACCOUNTS[api_key_id]["member_token"] = refreshed_token
                            last_error = e
                            continue
                    print(f"[RETRY] Re-login failed for account {account['email']}. Rotating to fresh account...")
                    mark_account_exhausted(api_key_id, account['email'])
                    last_error = e
                    continue
                # For any other unhandled exception in the loop
                last_error = e
                break

        if not result:
            db.update_task_status(task_id, 'failed')
            db.add_task_log(task_id, format_error_code(last_error))
            return

        if result.get("status") == "Done":
            completed_files = result.get("files", [])
            video_file = next((f for f in completed_files if ".mp4" in f.lower() and "thumbnail" not in f.lower()), None)
            dec_metadata = result.get("decryption_metadata")
            token_data_dict = {
                "member_token": current_token,
                "reference_images": params.get('reference_images', []),
                "reference_videos": params.get('reference_videos', []),
                "start_frame": params.get('start_frame'),
                "end_frame": params.get('end_frame')
            }
            if dec_metadata:
                token_data_dict.update({
                    "dec_aes_key": dec_metadata.get("aes_key"),
                    "dec_enc_key": dec_metadata.get("enc_key"),
                    "dec_enc_iv": dec_metadata.get("enc_iv"),
                    "dec_ts_ms": dec_metadata.get("ts_ms")
                })
            db.update_task_token(task_id, json.dumps(token_data_dict))

            if video_file:
                db.update_task_status(task_id, 'completed', make_proxy_url(video_file))
                deduct_api_key_quota(api_key_id, task_id, amount=model_api_credit)
            else:
                db.update_task_status(task_id, 'completed', make_proxy_url(completed_files[0]) if completed_files else "")
                deduct_api_key_quota(api_key_id, task_id, amount=model_api_credit)
            post_credits_info = get_member_remaining_credits(current_token)
            post_credits = post_credits_info.get("total_remain", "?") if post_credits_info else "?"
            print(f"[RENDER LOG] [VIDEO TASK: {task_id}] [TAMAMLANDI] -> Hesap: {account['email']} | Kalan Kredi: {post_credits}\n")
        elif result.get("status") == "Timeout":
            db.update_task_status(task_id, 'timeout')
            db.add_task_log(task_id, "504")
        else:
            db.update_task_status(task_id, 'failed')
            db.add_task_log(task_id, format_error_code(result.get('error')))

    except Exception as e:
        print(f"[ERROR] Video task {task_id} error: {e}")
        db.update_task_status(task_id, 'error')
        db.add_task_log(task_id, format_error_code(e))
    finally:
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

def process_tts_task(task_id, params, api_key_id):
    db.update_task_status(task_id, 'failed')
    db.add_task_log(task_id, "501")

def process_music_task(task_id, params, api_key_id):
    db.update_task_status(task_id, 'failed')
    db.add_task_log(task_id, "501")

def get_tts_voices(api_key_id):
    return [], "TTS not supported by this service"



def proxy_request(url, range_header=None):
    """Local or HTTP Proxy implementation for serving files."""
    import urllib.parse as urlparse
    import json
    import re
    import base64

    # 1. Clean double proxy url prefix
    while True:
        if "/proxy?url=" in url:
            parsed_temp = urlparse.urlparse(url)
            params_temp = urlparse.parse_qs(parsed_temp.query)
            nested_url = params_temp.get("url", [None])[0]
            if nested_url:
                url = nested_url
                continue
        break

    if not url.startswith("http://") and not url.startswith("https://"):
        # Local file path
        if os.path.exists(url):
            file_size = os.path.getsize(url)
            def iter_file():
                with open(url, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        yield chunk
            mime_type = "video/mp4" if url.endswith(".mp4") else "image/jpeg"
            headers = [
                ("Content-Type", mime_type),
                ("Content-Length", str(file_size)),
                ("Accept-Ranges", "bytes")
            ]
            return iter_file(), 200, headers
        else:
            return iter([]), 404, []

    # 2. Check if this is a private MyEdit S3 URL
    is_myedit_s3 = "cl-aol-media" in url or "cyberlink" in url
    
    if is_myedit_s3:
        import hashlib
        parsed_url = urlparse.urlparse(url)
        url_path = parsed_url.path  # e.g. /Vgen/results/Credit/59723825/thumbnail.jpg or /source/Tti/2zcmqgbdbdrks/input.1.jpg
        
        # Create MD5 hash of the url_path to serve as a unique, safe filename
        url_path_hash = hashlib.md5(url_path.encode('utf-8')).hexdigest()
        ext = ".mp4" if url_path.lower().endswith(".mp4") else ".jpg"
        
        cache_dir = "cache"
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except Exception:
                pass
        
        local_cache_path = os.path.join(cache_dir, f"{url_path_hash}{ext}")

        # A. If already cached locally, stream it directly from disk (supports seek/range!)
        if os.path.exists(local_cache_path):
            file_size = os.path.getsize(local_cache_path)
            mime_type = "video/mp4" if ext == ".mp4" else "image/jpeg"
            headers = [
                ("Content-Type", mime_type),
                ("Accept-Ranges", "bytes")
            ]
            
            start = 0
            end = file_size - 1
            status_code = 200

            if range_header and range_header.startswith("bytes="):
                try:
                    ranges = range_header.replace("bytes=", "").split("-")
                    if ranges[0]:
                        start = int(ranges[0])
                    if len(ranges) > 1 and ranges[1]:
                        end = int(ranges[1])
                    status_code = 206
                    headers.append(("Content-Range", f"bytes {start}-{end}/{file_size}"))
                except Exception:
                    pass

            headers.append(("Content-Length", str(end - start + 1)))

            def iter_cached_file():
                with open(local_cache_path, "rb") as f:
                    f.seek(start)
                    offset = start
                    while offset <= end:
                        chunk_end = min(offset + 8192, end + 1)
                        chunk = f.read(chunk_end - offset)
                        if not chunk:
                            break
                        yield chunk
                        offset += len(chunk)

            return iter_cached_file(), status_code, headers

        # B. If not cached, lookup task in database to fetch decryption keys / base64
        conn = db.get_connection()
        cursor = conn.cursor()
        task_row = None
        try:
            # We look for url_path in result_url or reference_image_urls (raw or url-encoded)
            query_val = f"%{url_path}%"
            query_val_enc = f"%{urlparse.quote(url_path, safe='')}%"
            if db.DB_TYPE == 'postgresql':
                cursor.execute('SELECT token FROM tasks WHERE result_url LIKE %s OR result_url LIKE %s OR reference_image_urls LIKE %s OR reference_image_urls LIKE %s', (query_val, query_val_enc, query_val, query_val_enc))
            else:
                cursor.execute('SELECT token FROM tasks WHERE result_url LIKE ? OR result_url LIKE ? OR reference_image_urls LIKE ? OR reference_image_urls LIKE ?', (query_val, query_val_enc, query_val, query_val_enc))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    task_row = row.get("token")
                elif isinstance(row, tuple) or isinstance(row, list):
                    task_row = row[0]
                else:
                    task_row = getattr(row, "token", None)
        except Exception as e:
            print(f"Proxy db query error: {e}")
        finally:
            cursor.close()
            conn.close()

        if task_row:
            try:
                task_data = json.loads(task_row)
            except Exception:
                task_data = {}

            # Case B1: Requesting a reference image/video from the database
            if "source" in url_path or "input." in url_path:
                filename = os.path.basename(url_path)
                match = re.search(r'(?:input\.|source_)(\d+)', filename)
                idx = 0
                if match:
                    if "input." in filename:
                        idx = int(match.group(1)) - 1
                    else:
                        idx = int(match.group(1))
                    if idx < 0:
                        idx = 0
                elif "first" in filename:
                    idx = 0
                elif "end" in filename:
                    idx = 1

                images = task_data.get("reference_images", [])
                videos = task_data.get("reference_videos", [])
                start_frame = task_data.get("start_frame")
                end_frame = task_data.get("end_frame")

                b64_data = None
                mime_type = "image/jpeg"

                is_first = ("first" in filename) or (idx == 0 and ("input.1" in filename or "source_0" in filename))
                is_end = ("end" in filename) or (idx == 1 and ("input.2" in filename or "source_1" in filename))

                if is_first and start_frame:
                    b64_data = start_frame
                elif is_end and end_frame:
                    b64_data = end_frame
                elif "video" in filename or filename.endswith(".mp4"):
                    if idx < len(videos):
                        b64_data = videos[idx]
                        mime_type = "video/mp4"
                else:
                    if idx < len(images):
                        b64_data = images[idx]
                    elif idx == 0 and start_frame:
                        b64_data = start_frame
                    elif idx == 1 and end_frame:
                        b64_data = end_frame

                if b64_data:
                    if "," in b64_data:
                        b64_data = b64_data.split(",")[1]
                    media_bytes = base64.b64decode(b64_data)
                    
                    # Write decoded data to local cache
                    try:
                        with open(local_cache_path, "wb") as f:
                            f.write(media_bytes)
                    except Exception:
                        pass

                    file_size = len(media_bytes)
                    headers = [
                        ("Content-Type", mime_type),
                        ("Content-Length", str(file_size)),
                        ("Accept-Ranges", "bytes")
                    ]
                    def iter_bytes():
                        for offset in range(0, file_size, 8192):
                            yield media_bytes[offset:offset+8192]
                    return iter_bytes(), 200, headers
                else:
                    return iter([]), 404, []

            # Case B2: Requesting a VGEN result video/image (requires decryption if keys are present)
            dec_aes_key = task_data.get("dec_aes_key")
            dec_enc_key = task_data.get("dec_enc_key")
            dec_enc_iv = task_data.get("dec_enc_iv")
            dec_ts_ms = task_data.get("dec_ts_ms")

            try:
                fwd_headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
                }
                resp = requests.get(url, headers=fwd_headers, timeout=60)
                resp.raise_for_status()
                raw_bytes = resp.content

                if dec_aes_key and dec_enc_key and dec_enc_iv and dec_ts_ms:
                    try:
                        # File is encrypted, decrypt it
                        aes_key = bytes.fromhex(dec_aes_key)
                        dec_enc_key = dec_enc_key.replace(" ", "+")
                        dec_enc_iv = dec_enc_iv.replace(" ", "+")

                        raw_key = decrypt_myedit_aes_gcm(aes_key, dec_enc_key, int(dec_ts_ms), 0)
                        raw_iv = decrypt_myedit_aes_gcm(aes_key, dec_enc_iv, int(dec_ts_ms), 0)
                        aesgcm = AESGCM(raw_key)
                        decrypted_bytes = aesgcm.decrypt(raw_iv, raw_bytes, None)
                    except Exception as dec_err:
                        print(f"Decryption failed (might be unencrypted thumbnail/media): {dec_err}")
                        decrypted_bytes = raw_bytes
                else:
                    # File is not encrypted, use raw bytes directly
                    decrypted_bytes = raw_bytes

                # Write to local cache
                try:
                    with open(local_cache_path, "wb") as f:
                        f.write(decrypted_bytes)
                except Exception:
                    pass

                file_size = len(decrypted_bytes)
                mime_type = "video/mp4" if url_path.lower().endswith(".mp4") else "image/jpeg"

                headers = [
                    ("Content-Type", mime_type),
                    ("Accept-Ranges", "bytes")
                ]

                start = 0
                end = file_size - 1
                status_code = 200

                if range_header and range_header.startswith("bytes="):
                    try:
                        ranges = range_header.replace("bytes=", "").split("-")
                        if ranges[0]:
                            start = int(ranges[0])
                        if len(ranges) > 1 and ranges[1]:
                            end = int(ranges[1])
                        status_code = 206
                        headers.append(("Content-Range", f"bytes {start}-{end}/{file_size}"))
                    except Exception:
                        pass

                headers.append(("Content-Length", str(end - start + 1)))

                def iter_bytes():
                    offset = start
                    while offset <= end:
                        chunk_end = min(offset + 8192, end + 1)
                        yield decrypted_bytes[offset:chunk_end]
                        offset = chunk_end

                return iter_bytes(), status_code, headers
            except Exception as e:
                print(f"Proxy fetch/decryption error: {e}")
                return iter([]), 500, []

        return iter([]), 404, []

    # 3. Standard HTTP url streaming proxy (for other non-MyEdit URLs)
    fwd_headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    }
    if range_header:
        fwd_headers['Range'] = range_header
    r = requests.get(url, headers=fwd_headers, stream=True, timeout=(30, 120))
    excluded = {'content-encoding', 'transfer-encoding', 'connection'}
    resp_headers = [(k, v) for k, v in r.headers.items() if k.lower() not in excluded]
    return r.iter_content(chunk_size=8192), r.status_code, resp_headers

# --- Recovery Logic ---

def resume_incomplete_tasks():
    print("=" * 50)
    print("[STARTUP] Starting crash recovery for MyEdit service...")
    try:
        recovery_result = db.recover_stale_tasks()
        if recovery_result['failed_count'] > 0:
            print(f"[STARTUP] Marked {recovery_result['failed_count']} tasks as failed (never logged in)")
    except Exception as e:
        print(f"[STARTUP] Error during stale task recovery: {e}")
        recovery_result = {'needs_check': []}

    needs_check = recovery_result.get('needs_check', [])
    for t in needs_check:
        db.update_task_status(t['task_id'], 'failed')
        if t.get('account_email') and t.get('api_key_id'):
            db.release_account(t['api_key_id'], t['account_email'])

    try:
        tasks = db.get_incomplete_tasks()
        for t in tasks:
            db.update_task_status(t['task_id'], 'failed')
            if t.get('account_email') and t.get('api_key_id'):
                db.release_account(t['api_key_id'], t['account_email'])
    except Exception as e:
        print(f"[STARTUP] Error during task resume: {e}")
    print("[STARTUP] Crash recovery complete.")
    print("=" * 50)
