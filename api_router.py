               
                                                              
                   
                                                              
       
                                    
                                                  
                             
                                       
                                 
 
         
                                                              
                             
          
                        
           
           
                   
 
                       
                                      
                          
                                                              

import requests
from openai import OpenAI


                                                              
         
                                                              
         
                             
                          
 
     
                        
                                       
                     
                       
                                                              
SILLY_HEADERS = {
    "User-Agent": "SillyTavern/1.12.0",
    "Referer": "http://localhost:8000/",
    "Origin": "http://localhost:8000",
    "X-Requested-With": "XMLHttpRequest",
}


def resolve_api_config(config, use_background):























    main_conf = {
        "api_type": config.get("api_type", "openai").lower(),
        "api_key": config.get("api_key", ""),
        "base_url": config.get("base_url", ""),
        "target_model": config.get("target_model", ""),
        "timeout": float(config.get("api_timeout", 120.0)),
        "route_name": "main"
    }

                                 
    if not use_background or not config.get("background_use_separate", False):
        return main_conf

    bg_conf = {
        "api_type": config.get("background_api_type", main_conf["api_type"]).lower(),
        "api_key": config.get("background_api_key", main_conf["api_key"]),
        "base_url": config.get("background_base_url", main_conf["base_url"]),
        "target_model": config.get("background_target_model", main_conf["target_model"]),
        "timeout": float(config.get("background_api_timeout", 60.0)),
        "route_name": "background"
    }

                                                                  
           
                            
                                 
                                                                  
    if not bg_conf["base_url"]:
        bg_conf["base_url"] = main_conf["base_url"]

    if not bg_conf["target_model"]:
        bg_conf["target_model"] = main_conf["target_model"]

    if not bg_conf["api_type"]:
        bg_conf["api_type"] = main_conf["api_type"]

    return bg_conf


def create_openai_client(config, use_background = False, timeout = None):


















    api_conf = resolve_api_config(config, use_background=use_background)

    return OpenAI(
        api_key=api_conf["api_key"],
        base_url=api_conf["base_url"],
        default_headers=SILLY_HEADERS,
        timeout=timeout if timeout is not None else api_conf["timeout"]
    )


def normalize_ollama_chat_url(base_url):









    base_url = (base_url or "").rstrip("/")
    if not base_url.endswith("/api/chat"):
        base_url = f"{base_url}/api/chat"
    return base_url


def build_http_headers(api_key = ""):







    headers = {
        "Content-Type": "application/json",
        **SILLY_HEADERS
    }

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


def log_route(api_conf, purpose = ""):







    prefix = "🧭 [API路由]"
    route_name = api_conf.get("route_name", "unknown")
    api_type = api_conf.get("api_type", "unknown")
    target_model = api_conf.get("target_model", "")
    purpose_text = f" | 用途={purpose}" if purpose else ""

    print(f"{prefix} route={route_name} | type={api_type} | model={target_model}{purpose_text}")


def chat_once(config, messages, temperature = 0.3, timeout = None, use_background = False, purpose = ""):





















    api_conf = resolve_api_config(config, use_background=use_background)
    actual_timeout = timeout if timeout is not None else api_conf["timeout"]

                                         

    if api_conf["api_type"] == "openai":
        client = create_openai_client(
            config=config,
            use_background=use_background,
            timeout=actual_timeout
        )

        resp = client.chat.completions.create(
            model=api_conf["target_model"],
            messages=messages,
            temperature=temperature
        )

        return (resp.choices[0].message.content or "").strip()

    elif api_conf["api_type"] == "ollama":
        url = normalize_ollama_chat_url(api_conf["base_url"])
        payload = {
            "model": api_conf["target_model"],
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        headers = build_http_headers(api_conf["api_key"])

        resp = requests.post(url, json=payload, headers=headers, timeout=actual_timeout)
        resp.raise_for_status()

        data = resp.json()
        return data.get("message", {}).get("content", "").strip()

    else:
        raise ValueError(f"不支持的 api_type: {api_conf['api_type']}")

                                                              
         
                                                              
       
                                            
                              
                                                  
                                        
                                                              
_vision_client = None

def create_vision_client(config, timeout=None):

    api_key = config.get("vision_api_key", "") or config.get("api_key", "")
    base_url = config.get("vision_base_url", "") or config.get("base_url", "")

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers=SILLY_HEADERS,
        timeout=timeout if timeout is not None
                else float(config.get("vision_api_timeout", 90.0))
    )

def get_vision_client(config):
    global _vision_client
    if _vision_client is None:
        _vision_client = create_vision_client(config)
    return _vision_client

def reset_vision_client():
    global _vision_client
    _vision_client = None

def has_separate_vision_api(config):
    return bool(
        config.get("vision_base_url") and config.get("vision_target_model")
    )