           
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles                    
from fastapi.responses import FileResponse                          
from fastapi import Request
from contextlib import asynccontextmanager                
import json
import datetime
import time                          
import re
import asyncio
import random
import os
import base64                      
import requests                 
import glob            

import llm_brain
import memory_manager
import motion_manager
import outfit_manager
import story_manager
import lorebook_manager

import builtins
import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
                                                        
    global main_loop
    main_loop = asyncio.get_running_loop()              

    print("\n" + "=" * 50)
    now_hour = datetime.datetime.now().hour
    if 5 <= now_hour < 12: time_tag, time_desc = "晨光微露", "清晨的微光中"
    elif 12 <= now_hour < 18: time_tag, time_desc = "午后静谧", "温暖的午后"
    elif 18 <= now_hour < 23: time_tag, time_desc = "夜色温柔", "夜幕降临"
    else: time_tag, time_desc = "夜半幽静", "深夜的寂静中"

    print(f"🌸 [{time_tag}] {time_desc}，正在等待她慢慢回过神来...")
    print("   (她似乎有些迷糊，需要几秒的时间才能完全清醒，请耐心等待)")
    try:
                             
                                                         
        current_int = llm_brain.config.get("intimacy", 0)              
        memory_manager.retrieve_relevant_memories("初次相遇的预热", current_int)             
        print(f"✨ [{time_tag}] 她慢慢睁开了眼睛，你看到了她的身影。")
    except Exception as e:
        print(f"⚠️ [{time_tag}] 刚醒来似乎有些头晕，但并不影响你们的相遇: {e}")
    print("=" * 50 + "\n")

                                  
    yield

                                                         
                                           
    print("\n💤 [世界法则]: 服务器正在休眠，晚安。")

class IgnoreStaticFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        ignored_keywords = [
            'GET /model/',
            'GET /js/',
            'GET /audio/',
            'GET /favicon.ico',
            'GET /apple-touch-icon',
        ]
        return not any(k in msg for k in ignored_keywords)

                
app = FastAPI(lifespan=lifespan)

                                         
app.state.auto_outfit_locked = False
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(IgnoreStaticFilter())

                                 
os.makedirs(os.path.join("web", "audio"), exist_ok=True)
app.mount("/audio", StaticFiles(directory="web/audio"), name="audio")

                                            
                         
                                            
connected_clients = set()                       
terminal_history = []                       
main_loop = None
_original_print = builtins.print


def global_print(*args, **kwargs):
                            
    _original_print(*args, **kwargs)

    if not main_loop: return

    text = " ".join(str(a) for a in args)
    if not text.strip():
        return

                
    html_text = text.replace('\n', '<br>')
    terminal_history.append(html_text)
    if len(terminal_history) > 200:
        terminal_history.pop(0)                   

                                        
    if not connected_clients: return

                           
    try:
        for ws in list(connected_clients):
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"action": "terminal", "text": html_text}),
                main_loop
            )
    except Exception:
        pass

                        
builtins.print = global_print

                                
app.state.current_time_period = "unknown"

                                            
                       
                                            
async def translate_to_japanese_async(text: str):
    def _translate():
        try:
            api_type = llm_brain.config.get("api_type", "openai").lower()
            messages = [
                {"role": "system",
                 "content": "你是一个精准的中译日翻译器，请将玩家的中文台词精准直译翻译成对应的日文。【极其重要】：如果文本中包含形如 [quick_breath]、[sigh] 等英文控制标签，你必须原样保留它们，并将它们插入到日文中合理的位置。绝对不要翻译这些方括号内的标签！只需要输出最终的日文结果，不要任何解释。"},
                {"role": "user", "content": text}
            ]
            if api_type == "openai":
                response = llm_brain.client.chat.completions.create(
                    model=llm_brain.TARGET_MODEL,
                    messages=messages,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            elif api_type == "ollama":
                base_url = llm_brain.config.get("base_url", "").rstrip('/')
                if not base_url.endswith('/api/chat'):
                    base_url = f"{base_url}/api/chat"
                payload = {"model": llm_brain.TARGET_MODEL, "messages": messages, "stream": False,
                           "options": {"temperature": 0.3}}
                headers = {"Content-Type": "application/json"}
                api_key = llm_brain.config.get("api_key", "")
                if api_key: headers["Authorization"] = f"Bearer {api_key}"
                resp = requests.post(base_url, json=payload, headers=headers, timeout=30.0)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", text).strip()
        except Exception as e:
            print(f"\n⚠️ [意识干扰]: 那种古老的语调在脑海中变得模糊，你只能靠直觉去理解她想表达的意思...")
            print(f"   (🛠️ 隐秘线索: 思绪转译受阻，已回退至熟悉的语言 - {str(e)[:50]})")
            return text

                                  
    return await asyncio.to_thread(_translate)


async def process_tts(raw_text: str):
             
                                        
    clean_text = re.sub(r'\[(act_|mood_|intimacy_|wear_|hair_|set_name_).*?\]', '', raw_text)
    clean_text = re.sub(r'（内心：.*?）', '', clean_text).strip()

    if not clean_text:
        return "", True, "empty"

                                                
                       
                                                
    audio_dir = os.path.join("web", "audio")
    try:
                         
        old_files = glob.glob(os.path.join(audio_dir, "temp_response_*.wav"))
                                  
        old_files.sort(key=os.path.getmtime)

                                         
        if len(old_files) > 5:
            for f in old_files[:-5]:
                try:
                    os.remove(f)
                except Exception:
                    pass                         
    except Exception as e:
        print(f"清理音频缓存失败: {e}")

    instruct_text = ""
                                       
    match = re.match(r'^(.*?)<\|endofprompt\|>(.*)$', clean_text, re.DOTALL)
    if match:
        raw_instruct = match.group(1)
                                           
        instruct_text = re.sub(r'[^\w\u4e00-\u9fa5]', '', raw_instruct)
        clean_text = match.group(2).strip()

             
    if llm_brain.config.get("tts_translate_to_ja", False) and clean_text:
        print("\n🌐 [古老回音]: 她的嘴唇微动，吐出的似乎是前文明遗留下的某种古老而温柔的语调...")
        clean_text = await translate_to_japanese_async(clean_text)
        print(f"   (✨ 呢喃: {clean_text})")

                  
    def _tts_request():
        try:
            tts_engine = llm_brain.config.get("tts_engine", "cosyvoice")
            proxies = {"http": None, "https": None}

            if tts_engine == "cosyvoice":
                url = llm_brain.config.get("cosy_url", "")
                payload = {
                    "text": clean_text,
                    "character_name": llm_brain.config.get("cosy_character", ""),
                    "mode": llm_brain.config.get("cosy_mode", ""),
                    "instruct_text": instruct_text,
                    "speed": 1.0
                }
                response = requests.post(url, json=payload, proxies=proxies, timeout=(3.0, 60.0))
                if response.status_code == 200:
                                                      
                                    
                    current_timestamp = int(time.time() * 1000)
                    audio_filename = f"temp_response_{current_timestamp}.wav"
                    audio_path = os.path.join("web", "audio", audio_filename)
                    with open(audio_path, "wb") as f:
                        f.write(response.content)
                                         
                    return f"/audio/{audio_filename}?t={current_timestamp}", True, "success"
                else:
                    print(
                        f"\n🔇 [感官剥离]: 也许是基地的磁场干扰，或者是她太过紧张，她的声音细若游丝，瞬间消散在冰冷的空气中...")
                    print(f"   (🛠️ 隐秘线索: 发声器官(CosyVoice)共振失败，状态码 {response.status_code})")
                    return "", False, "api_error"
            else:
                sovits_text = re.sub(r'^.*?<\|endofprompt\|>', '', clean_text)
                sovits_text = re.sub(r'\[.*?\]', '', sovits_text).strip()
                url = llm_brain.config.get("sovits_url", "")
                params = {
                    "refer_wav_path": llm_brain.config.get("sovits_ref_audio", ""),
                    "prompt_text": llm_brain.config.get("sovits_ref_text", ""),
                    "prompt_language": llm_brain.config.get("sovits_ref_lang", ""),
                    "text": sovits_text,
                    "text_language": llm_brain.config.get("sovits_target_lang", "")
                }
                response = requests.get(url, params=params, proxies=proxies, timeout=(3.0, 60.0))
                if response.status_code == 200:
                                                      
                                    
                    current_timestamp = int(time.time() * 1000)
                    audio_filename = f"temp_response_{current_timestamp}.wav"
                    audio_path = os.path.join("web", "audio", audio_filename)
                    with open(audio_path, "wb") as f:
                        f.write(response.content)
                                         
                    return f"/audio/{audio_filename}?t={current_timestamp}", True, "success"
                else:
                    print(f"\n🔇 [听觉迷雾]: 她的声音似乎被某种无形的屏障阻挡了...")
                    print(
                        f"   (🛠️ 隐秘线索: API拒绝了请求，状态码 {response.status_code}，原因: {response.text[:100]})")
                    return "", False, "api_error"


        except requests.exceptions.ConnectionError:
            print(f"\n🔇 [听觉迷雾]: 周围的环境有些嘈杂，你只能看着她微动的双唇，却听不清声音。")
            print(f"   (🛠️ 隐秘线索: GPT-SoVITS/CosyVoice API未启动或端口错误，已瞬间触发防卡死保护！)")
            return "", False, "connection_error"
        except requests.exceptions.ProxyError:
            print(f"\n🔇 [听觉迷雾]: 一阵莫名的耳鸣让你短暂失聪，无法听清她的话语...")
            print(f"   (🛠️ 隐秘线索: 网络代理干扰了本地连接，尝试关闭代理软件)")
            return "", False, "proxy_error"
        except requests.exceptions.Timeout:
            print(f"\n🔇 [听觉迷雾]: 她似乎在犹豫，声音卡在了喉咙里，过了好一会都没能发出声来...")
            print(f"   (🛠️ 隐秘线索: 处理超过了 60 秒。因为电脑配置较差，显卡可能仍在加载模型，请耐心再跟她聊一句试试)")
            return "", False, "timeout"
        except Exception as e:
            print(f"\n🔇 [听觉迷雾]: 也许是太紧张了，她的声音细若游丝，几乎无法捕捉...")
            print(f"   (🛠️ 隐秘线索: 底层连接失败，错误详情: {str(e)[:150]})")
            return "", False, "unknown_error"

    return await asyncio.to_thread(_tts_request)

                                              
@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
                                                
    if request.url.path.startswith("/model/") or request.url.path.startswith("/js/"):
        response.headers["Cache-Control"] = "public, max-age=31536000"
    return response

                                            
                               
                                            
                                  
app.mount("/model", StaticFiles(directory="web/model"), name="model")

                                     
if os.path.exists("web/js"):
    app.mount("/js", StaticFiles(directory="web/js"), name="js")

                                            
@app.get("/")
async def get_index():
    return FileResponse("web/index.html")

                               
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("web/favicon.ico")

                          
@app.get("/download_novel")
async def download_novel():
    file_path = os.path.join("world_data", "novel_log.txt")
    if os.path.exists(file_path):
                      
        return FileResponse(file_path, filename="Romasha_Story_Log.txt", media_type="application/octet-stream")
    return {"error": "暂无推演记录"}


                            
async def revert_motion_task(websocket: WebSocket, state: dict):
    await asyncio.sleep(4.5)
    try:
                                                                 
        await websocket.send_json({"action": "param", "id": "ParamCheek", "value": -99})
        await websocket.send_json({"action": "param", "id": "angry", "value": -99})
        await websocket.send_json({"action": "motion", "group": "BaseMotions", "index": state["current_idle_motion"]})
    except Exception:
        pass


                      
                         
                           

               
llm_lock = asyncio.Lock()

async def execute_tag(websocket: WebSocket, tag: str, state_dict: dict):
    try:
        if tag.startswith('set_name_'):
            new_name = tag[9:].strip()
            llm_brain.config["player_name"] = new_name
            llm_brain.save_config()
            print(f"\n📝 [羁绊铭记]: 已将你的称呼更新为：{new_name}")

                                           
            await websocket.send_json({"action": "update_name_btn", "name": new_name})
            bubble_html = f"<span style='color:#6031e2; font-size: var(--sub-font-size);'><i>(她在心里默默记下了你的名字：{new_name})</i></span><br>"
            state_dict["current_context_html"] += bubble_html
            return                  

                                 
        elif tag.startswith('move_to_'):
            new_loc = tag[8:].strip()                      
            if new_loc:
                llm_brain.config["current_location"] = new_loc
                llm_brain.save_config()
                print(f"\n🚶‍♀️ [空间转移]: 伴随着脚步声，Romasha 前往了【{new_loc}】。")

                                              
                bubble_html = f"<span style='color:#6031e2; font-size: var(--sub-font-size);'><i>(她改变了位置，现在来到了：{new_loc}...)</i></span><br>"
                state_dict["current_context_html"] += bubble_html

                                               
                                                          
                asyncio.create_task(websocket.send_json({
                    "action": "sys_bubble",
                    "html": f"<span style='color:#3498db; font-weight:bold; font-size: var(--main-font-size);'>🚶‍♀️ 场景转移：前往【{new_loc}】...</span>",
                    "duration": 4000              
                }))
            return

        if tag.startswith('intimacy_'):
            val_str = tag.split('_', 1)[1]
            change_val = int(val_str)
            current_int = llm_brain.config.get("intimacy", 0)
            new_int = max(-100, min(100, current_int + change_val))

            llm_brain.config["intimacy"] = new_int
            llm_brain.save_config()

            symbol = "+" if change_val >= 0 else ""
            print(f"💖 [关系动态]: 亲密度 {symbol}{change_val} (当前: {new_int}/100)")

            color = "#ffb6c1" if change_val >= 0 else "#a8d8ea"
                                             
            intimacy_html = f"<span style='color:{color}; font-size: var(--sub-font-size);'><i>[亲密度 {symbol}{change_val}]</i></span><br>"
            state_dict["current_context_html"] += intimacy_html

        elif tag.startswith('hair_'):
            hair_style = tag.split('_', 1)[1]
            params = outfit_manager.get_outfit_params(outfit_manager._current_outfit, hair_style)
            for k, v in params.items(): await websocket.send_json({"action": "param", "id": k, "value": v})

        elif tag.startswith('wear_'):
            outfit_name = tag.split('_', 1)[1]
            params = outfit_manager.get_outfit_params(outfit_name)
            for k, v in params.items(): await websocket.send_json({"action": "param", "id": k, "value": v})
                                
            app.state.auto_outfit_locked = True

        elif tag.startswith('mood_'):
            mood_name = tag.split('_', 1)[1]
            idx = motion_manager.get_motion_index(mood_name)
            if idx is not None:
                state_dict["current_idle_motion"] = idx
                await websocket.send_json({"action": "idle_motion", "group": "BaseMotions", "index": idx})

                                  
            if mood_name in ['neutral', 'wait', 'wait_haji']:
                state_dict['is_current_mood_static'] = True
            else:
                state_dict['is_current_mood_static'] = False
                state_dict['static_mood_time'] = -1

        elif tag.startswith('act_'):
            action_name = tag.split('_', 1)[1]
                                                  
            if action_name == 'taol_fall':
                print("\n💦 [突发状况]: 浴巾好像松开了！她慌乱地试图遮掩...")
                state_dict['taol_recover_time'] = 8

            idx = motion_manager.get_motion_index(action_name)
            if idx is not None:
                await websocket.send_json({"action": "motion", "group": "BaseMotions", "index": idx})
                                                        
                                                                                

    except Exception as e:
        pass


async def check_and_apply_outfit(websocket: WebSocket, is_initial=False):
                                            
    now = datetime.datetime.now()
    month, day, hour = now.month, now.day, now.hour

                             
    holidays = {
        (1, 1): "元旦", (2, 14): "情人节", (3, 8): "妇女节", (4, 1): "愚人节",
        (5, 1): "劳动节", (5, 4): "青年节", (6, 1): "儿童节", (8, 1): "建军节",
        (9, 10): "教师节", (10, 1): "国庆节", (10, 31): "万圣节", (11, 11): "光棍节",
        (12, 24): "平安夜", (12, 25): "圣诞节", (12, 31): "跨年夜"
    }

    is_holiday = (month, day) in holidays
    is_cold = month in [10, 11, 12, 1, 2, 3]
    current_intimacy = llm_brain.config.get("intimacy", 0)

    target_outfit = None
    new_time_period = "day"

                                            
    if is_holiday:
        new_time_period = f"holiday_{month}_{day}"
        if is_initial: print(f"\n🎉 [系统提醒]: 今天是 {holidays[(month, day)]}！Romasha 换上了节日服装。")
        target_outfit = "ethnic_cloak" if is_cold else "ethnic_wear"
    elif hour >= 22 or hour <= 6:
        if outfit_manager._current_outfit not in ["sleepwear", "towel"]:
            if current_intimacy >= 60 and random.random() < 0.35:
                                                           
                target_outfit = "towel"
            else:
                target_outfit = "sleepwear"
        else:
            target_outfit = outfit_manager._current_outfit
    elif hour >= 19:
        new_time_period = "evening"
        target_outfit = "uniform_dress"
    else:
        new_time_period = "day"
        target_outfit = "uniform_tight"

                                                 
    if is_initial:
        app.state.current_time_period = new_time_period
        params = outfit_manager.get_outfit_params(target_outfit)
        for k, v in params.items():
            await websocket.send_json({"action": "param", "id": k, "value": v})
        idx = motion_manager.get_motion_index('talk')
        await websocket.send_json({"action": "idle_motion", "group": "BaseMotions", "index": idx})
        return

                        
    if new_time_period != app.state.current_time_period:
        app.state.current_time_period = new_time_period

                                           
        if getattr(app.state, "auto_outfit_locked", False):
            if new_time_period == "day":
                app.state.auto_outfit_locked = False
            else:
                return                       

        if target_outfit and target_outfit != outfit_manager._current_outfit:
            if target_outfit == "towel":
                print(f"\n👗 [观察]: 夜深了，听到浴室传来隐约的水声后，Romasha裹着浴巾走了出来。")
            elif target_outfit == "sleepwear":
                print(f"\n👗 [观察]: 留意到时间的推移，Romasha默默换上了轻薄的睡衣。")
            else:
                print(f"\n👗 [观察]: 留意到时间的推移，Romasha默默换了一身适合现在的衣服。")

            await websocket.send_json({
                "action": "bubble",
                "html": "<span style='color:#ccc;'><i>(一阵轻微的窸窣声后，她换好了一身衣服...)</i></span><br>"
            })

                      
            async def delayed_apply():
                await asyncio.sleep(3)
                params = outfit_manager.get_outfit_params(target_outfit)
                for k, v in params.items():
                    await websocket.send_json({"action": "param", "id": k, "value": v})
                    await asyncio.sleep(0.05)

            asyncio.create_task(delayed_apply())


@app.websocket("/ws/romasha")
async def romasha_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)                 
    print("\n📱 手机客户端已接入神经链接！")

                                             
    await websocket.send_json({
        "action": "sync_config",
        "voice_enabled": llm_brain.config.get("voice_enabled", True),
        "tts_engine": llm_brain.config.get("tts_engine", "cosyvoice"),
        "bubble_size": llm_brain.config.get("bubble_size", 1),
        "ja_translate": llm_brain.config.get("tts_translate_to_ja", False),
                          
        "touch_enabled": llm_brain.config.get("touch_enabled", True),
        "track_enabled": llm_brain.config.get("track_enabled", True)
    })

                                 
    if terminal_history:
        history_html = "".join([f"<div>{line}</div>" for line in terminal_history])
        await websocket.send_json({"action": "terminal_history", "text": history_html})

    state = {
        "thought_idle_seconds": 0, "vision_idle_seconds": 0, "vision_sleep_count": 0,
        "next_idle_trigger_minutes": 3, "current_idle_target_seconds": 180,
        "static_mood_time": -1, "taol_recover_time": -1, "has_random_taol_fall": False,
        "is_tracking": True, "current_idle_motion": motion_manager.get_motion_index('talk'),
        "is_generating": False, "cancel_flag": False, "accumulated_text": "",                 
        "is_current_mood_static": False, "current_context_html": "",                    
        "audio_start_event": asyncio.Event(),                
        "thought_id_counter": 0,                 
                         
        "is_story_mode": False, "story_level": "1", "processed_tags": set(),                  
        "pending_story_options": []              
    }

                                     
    async def on_speech_finished():
        try:
            await websocket.send_json({"action": "param", "id": "ParamCheek", "value": -99})
            await websocket.send_json({"action": "param", "id": "angry", "value": -99})
            await websocket.send_json({"action": "idle_motion", "group": "BaseMotions", "index": state["current_idle_motion"]})

            if state.get("is_current_mood_static", False):
                delay_sec = 5 if llm_brain.config.get("voice_enabled", True) else 8
                state["static_mood_time"] = delay_sec

                                            
            if state.get("is_story_mode", False) and state.get("pending_story_options"):
                await websocket.send_json({
                    "action": "story_show_options",
                    "options": state["pending_story_options"]
                })
                state["pending_story_options"] = []         

        except RuntimeError:
                                                           
            pass
        except Exception:
            pass

    async def heartbeat_engine():
        routine_tick = 0
        while True:
            await asyncio.sleep(1)

                                                        
                               
                                       
                                     
                                                        
            routine_tick += 1
            if routine_tick >= 60:
                routine_tick = 0
                await check_and_apply_outfit(websocket, is_initial=False)

                                                
            if state.get("is_story_mode", False):
                continue

                                                            
            if state["taol_recover_time"] > 0:
                state["taol_recover_time"] -= 1
                if state["taol_recover_time"] == 0:
                    sys_prompt = "[系统机制：距离刚才浴巾意外滑落已经过去了整整10秒。你现在急忙蹲下重新捡起并紧紧裹好了浴巾。请必须输出 [wear_towel] 标签，并伴随极其娇羞、甚至带有哭腔或羞愤的动作（如 [mood_talk_ero]）与慌乱的话语/心声。]"
                    html_context = "<span style='color:#fd92a1;'><i>(短暂的慌乱后，她急急忙忙重新裹好了浴巾...)</i></span><br>"
                    loading_html = html_context + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(满脸通红手忙脚乱中...)</i></span>"
                    await websocket.send_json({"action": "bubble", "html": loading_html})

                                                        
                    if state["is_generating"]:
                        state["cancel_flag"] = True
                        await websocket.send_json({"action": "stop_audio"})
                        await asyncio.sleep(0.05)

                    state["thought_id_counter"] += 1
                    asyncio.create_task(
                        trigger_thought(sys_prompt, html_context, True, "", state["thought_id_counter"]))
                    state["taol_recover_time"] = -1

                               
            if state["static_mood_time"] > 0 and state["vision_idle_seconds"] < 300:
                state["static_mood_time"] -= 1
                if state["static_mood_time"] == 0:
                    sys_prompt = "[系统机制：你刚才已经维持静止发呆或小声嘀咕 15 秒了。请根据你此刻的情绪，决定切换回正常的动态常态动作（如 mood_talk, mood_talk_alc 等）。你可以小声嘟囔一句话、说一两句心声，也可以什么都不说只输出动作标签。]"
                    html_context = "<span style='color:#ccc;'><i>(短暂的定格后，她似乎有了动作...)</i></span><br>"
                    loading_html = html_context + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(调整状态...)</i></span>"
                    await websocket.send_json({"action": "bubble", "html": loading_html})

                                   
                    if state["is_generating"]:
                        state["cancel_flag"] = True
                        await websocket.send_json({"action": "stop_audio"})
                        await asyncio.sleep(0.05)

                    state["thought_id_counter"] += 1
                    asyncio.create_task(
                        trigger_thought(sys_prompt, html_context, True, "", state["thought_id_counter"]))
                    state["static_mood_time"] = -1

                                             
            if state["is_generating"]: continue

            state["thought_idle_seconds"] += 1
            state["vision_idle_seconds"] += 1
                              

            if state["vision_idle_seconds"] == 300:
                await websocket.send_json({"action": "tracking", "state": False})
                idx = motion_manager.get_motion_index('wait_haji')
                await websocket.send_json({"action": "idle_motion", "group": "BaseMotions", "index": idx})

                if state["vision_sleep_count"] == 0:
                    print(f"\n💤 [观察]: 经过一段时间的静默，Romasha收起思绪，沉浸到了自己的世界中。")
                elif state["vision_sleep_count"] == 1:
                    print(f"\n💤 [观察]: 刚才的挪动并没有引起Romasha进一步的注意，她的视线再次移开，继续发呆了。")
                else:
                    print(f"\n💤 [观察]: 仿佛已经习惯了这种无声的摆弄，Romasha只是安静地待在新的位置，依然没有看你。")
                state["vision_sleep_count"] += 1

            if state["thought_idle_seconds"] == state["current_idle_target_seconds"]:
                current_intimacy = llm_brain.config.get("intimacy", 0)
                if current_intimacy > 90 and outfit_manager._current_outfit == "towel" and not state[
                    "has_random_taol_fall"]:
                    if random.random() < 0.2:
                        state["has_random_taol_fall"] = True
                        sys_prompt = "[系统机制：由于长时间的安静，加上你的动作幅度，你身上裹着的浴巾突然意外滑落了！你完全没防备。请立刻输出带有 [act_taol_fall] 标签的动作反应，并伴随一句极其慌乱、娇羞的惊呼或心声。]"
                        state["thought_id_counter"] += 1
                        asyncio.create_task(trigger_thought(sys_prompt, "", True, "", state["thought_id_counter"]))
                        state["next_idle_trigger_minutes"] += random.randint(3, 10)
                        state["current_idle_target_seconds"] = state["thought_idle_seconds"] + (
                                    state["next_idle_trigger_minutes"] * 60)
                        continue

                minutes = state["thought_idle_seconds"] // 60
                                           
                if minutes == 3:
                    sys_prompt = "[系统机制：距离刚才的互动已经安静了整整 3 分钟。请结合刚才的对话氛围、彼此关系与当前情境，自主判断他现在的大致状态（例如仍在安静陪伴、只是暂时没有说话、在做自己的事，或已经离开）。请根据你此时真实的心情，输出一小段自言自语、轻声呢喃或内心独白（使用括号表示心声）。你可以保留刚才互动时的情绪余温，也可以自然改变动作；若你主观上拿不准，也可以表现出迟疑、安静感知或很轻的试探。注意：不要机械罗列可能性，而是直接给出符合你当下判断的自然反应。]"
                else:
                    sys_prompt = f"[系统机制：对方已经持续安静了 {minutes} 分钟。请根据这个时长、之前的对话上下文、当前时间氛围，以及你自身的直觉，自主推断他现在的状态（例如仍在身边沉默、已经睡着、暂时离开、或你只能感觉到他的存在感已经变淡）。你的视线可以自然移开，不必一直看着他。此时你可以选择让情绪渐渐平复（切换回普通的 talk 等待机动作），或者继续沉浸在自己的世界里小声嘀咕、发呆。请给出一小段符合你当前主观判断的心声、自言自语或动作反应。注意：不要把判断说得像系统播报，应像一个真实的人凭感觉作出的自然反应。]"

                html_context = "<span style='color:#ccc;'><i>(漫长的安静中，Romasha 似乎在想些什么...)</i></span><br>"
                loading_html = html_context + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(安静中...)</i></span>"
                await websocket.send_json({"action": "bubble", "html": loading_html})
                state["thought_id_counter"] += 1
                asyncio.create_task(trigger_thought(sys_prompt, html_context, True, "", state["thought_id_counter"]))

                state["next_idle_trigger_minutes"] += random.randint(3, 10)
                state["current_idle_target_seconds"] = state["thought_idle_seconds"] + (
                            state["next_idle_trigger_minutes"] * 60)

                                  
    async def trigger_thought(prompt: str, context_html: str, is_system=False, interrupted_text="", my_thought_id=0):
        async with llm_lock:
                                                                                 
            if state["thought_id_counter"] != my_thought_id:
                return

            try:
                state["is_generating"] = True
                state["cancel_flag"] = False
                state["accumulated_text"] = ""

                                                
                state["has_act_this_turn"] = False
                state["has_mood_this_turn"] = False

                                                  
                state["current_context_html"] = context_html

                voice_enabled = llm_brain.config.get("voice_enabled", True)
                pending_tags = []             

                                
                state["static_mood_time"] = -1

                if is_system:
                    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 🍃 [时光流逝]: {prompt[6:19]}...")
                else:
                    if not context_html.startswith("<span style='color:#ccc;'>"):
                        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 👤 你: {prompt}")

                current_display_text = ""
                processed_tags = set()
                final_clean_text = ""

                                              
                for chunk in llm_brain.stream_chat_generator(prompt, interrupted_text):
                    if state["cancel_flag"]:
                        print("💬 [观察]: 她的话音戛然而止，注意力瞬间被你刚才的举动吸引。")
                        return             

                    state["accumulated_text"] += chunk
                    tags = re.findall(r'\[(.*?)\]', state["accumulated_text"])
                    for tag in tags:
                        tag_lower = tag.lower()
                        if tag_lower not in processed_tags:
                            processed_tags.add(tag_lower)
                                                   
                            if tag_lower.startswith('intimacy_'):
                                await execute_tag(websocket, tag_lower, state)
                            elif tag_lower.startswith('set_name_'):                  
                                await execute_tag(websocket, tag, state)                                
                                                                        
                            elif tag_lower.startswith('act_'):
                                if not state.get("has_act_this_turn"):
                                    state["has_act_this_turn"] = True
                                    if voice_enabled:
                                        pending_tags.append(tag_lower)
                                    else:
                                        await execute_tag(websocket, tag_lower, state)

                            elif tag_lower.startswith('mood_'):
                                if not state.get("has_mood_this_turn"):
                                    state["has_mood_this_turn"] = True
                                    if voice_enabled:
                                        pending_tags.append(tag_lower)
                                    else:
                                        await execute_tag(websocket, tag_lower, state)

                            elif tag_lower.startswith(('wear_', 'hair_')):
                                if voice_enabled:
                                    pending_tags.append(tag_lower)
                                else:
                                    await execute_tag(websocket, tag_lower, state)

                    clean_text = re.sub(r'\[.*?\]', '', state["accumulated_text"])
                    clean_text = re.sub(r'^.*?<\|endofprompt\|>', '', clean_text)
                    final_clean_text = re.sub(r'\[[^\]]*$', '', clean_text).strip()

                    if voice_enabled:
                                                                               
                        loading_html = state[
                                           "current_context_html"] + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(微启双唇，正在酝酿要说的话...)</i></span>"
                        try:
                            await websocket.send_json({"action": "bubble", "html": loading_html})
                        except RuntimeError:
                            return
                    else:
                                      
                        while len(current_display_text) < len(final_clean_text):
                            if state["cancel_flag"]: return         
                            current_display_text += final_clean_text[len(current_display_text)]
                            safe_text = current_display_text.replace("\n", "<br>")
                            try:
                                await websocket.send_json(
                                    {"action": "bubble", "html": state["current_context_html"] + safe_text})
                            except RuntimeError:
                                return
                            await asyncio.sleep(0.04)

                                                            
                                          
                if state["accumulated_text"].strip() and not state["cancel_flag"]:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🌸 Romasha: {state['accumulated_text']}")

                    if voice_enabled:
                        audio_base64, success, status = await process_tts(state["accumulated_text"])

                                                                         
                        if state["cancel_flag"]:
                            return

                                                            
                                                                     
                        if state["thought_id_counter"] != my_thought_id:
                            print("👻 [系统拦截]: 捕获到上一轮的幽灵 TTS 语音，已将其销毁！")
                            return

                        if success:
                            if audio_base64:                   
                                                      
                                state["audio_start_event"].clear()
                                                                
                                await websocket.send_json({"action": "play_audio", "url": audio_base64})

                                                                   
                                try:
                                                                                             
                                    await asyncio.wait_for(state["audio_start_event"].wait(), timeout=30.0)
                                except asyncio.TimeoutError:
                                                                    
                                    print("⚠️ [网络延迟]: 手机端长时间未完成音频接收，似乎遇到了网络瓶颈...")
                                    pass

                                                   
                                if state["cancel_flag"]: return

                                                                       
                                for tag in pending_tags:
                                    await execute_tag(websocket, tag, state)

                                                                
                                while len(current_display_text) < len(final_clean_text):
                                    if state["cancel_flag"]: return         
                                    current_display_text += final_clean_text[len(current_display_text)]
                                    safe_text = current_display_text.replace("\n", "<br>")
                                    try:
                                        await websocket.send_json(
                                            {"action": "bubble", "html": state["current_context_html"] + safe_text})
                                    except RuntimeError:
                                        return
                                    await asyncio.sleep(0.04)

                            else:
                                                                      
                                              
                                for tag in pending_tags:
                                    await execute_tag(websocket, tag, state)

                                                    
                                async def mock_audio_end_empty():
                                    await asyncio.sleep(2.0)
                                                                             
                                    if state["thought_id_counter"] == my_thought_id and not state["cancel_flag"]:
                                        await on_speech_finished()

                                asyncio.create_task(mock_audio_end_empty())

                                while len(current_display_text) < len(final_clean_text):
                                    if state["cancel_flag"]: return
                                    current_display_text += final_clean_text[len(current_display_text)]
                                    safe_text = current_display_text.replace("\n", "<br>")
                                    try:
                                        await websocket.send_json(
                                            {"action": "bubble", "html": state["current_context_html"] + safe_text})
                                    except RuntimeError:
                                        return
                                    await asyncio.sleep(0.04)

                        else:
                                                             
                            for tag in pending_tags:
                                await execute_tag(websocket, tag, state)

                            if status == "connection_error":
                                llm_brain.config["voice_enabled"] = False
                                llm_brain.save_config()
                                print(
                                    "\n💭 [感官适应]: 你决定不再强求听清每一个字，而是专心注视着她。(若想再次尝试倾听，可对她输入 /voice 1)")
                                await websocket.send_json({"action": "bubble", "html": state[
                                                                                               "current_context_html"] + "<span style='color:#e74c3c; font-size: var(--sub-font-size);'><i>(环境有些喧嚣，你注视着她微动的双唇，读懂了她的话语...)</i></span><br>"})
                                                                   
                                await websocket.send_json({"action": "sync_config", "voice_enabled": False})
                            else:
                                await websocket.send_json({"action": "bubble", "html": state[
                                                                                               "current_context_html"] + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(你努力分辨着她微弱的声音...)</i></span><br>"})

                                                                       
                            duration = max(4.0, len(final_clean_text) * 0.25)

                            async def mock_audio_end():
                                await asyncio.sleep(duration)
                                          
                                                      
                                                 
                                                                    
                                if state["thought_id_counter"] == my_thought_id and not state["cancel_flag"]:
                                    await on_speech_finished()

                            asyncio.create_task(mock_audio_end())

                                                 
                            while len(current_display_text) < len(final_clean_text):
                                if state["cancel_flag"]: return         
                                current_display_text += final_clean_text[len(current_display_text)]
                                safe_text = current_display_text.replace("\n", "<br>")
                                try:
                                    await websocket.send_json({"action": "bubble", "html": context_html + safe_text})
                                except RuntimeError:
                                    return
                                await asyncio.sleep(0.04)

                    else:
                                           
                        duration = max(4.0, len(final_clean_text) * 0.25)

                        async def mock_audio_end_no_voice():
                            await asyncio.sleep(duration)
                                             
                                                                
                            if state["thought_id_counter"] == my_thought_id and not state["cancel_flag"]:
                                await on_speech_finished()

                        asyncio.create_task(mock_audio_end_no_voice())

            finally:
                                                              
                state["is_generating"] = False
                try:
                    await websocket.send_json({"action": "touch_unlock"})
                except Exception:
                    pass

                                                
                     
                                                
    async def trigger_story_thought(level: str, choice_text: str, my_thought_id: int):
        async with llm_lock:
            if state["thought_id_counter"] != my_thought_id:
                return

            try:
                state["is_generating"] = True
                state["cancel_flag"] = False
                state["processed_tags"].clear()

                voice_enabled = llm_brain.config.get("voice_enabled", True)

                              
                desc_text = f"▶ 抉择: {choice_text}" if choice_text else f"▶ 开启世界线推演 (参与度: {level})"
                await websocket.send_json({"action": "story_prepare", "desc": desc_text})

                                                                                     
                bubble_html = "<span style='color:#6031e2; font-size: var(--sub-font-size);'><i>(正在进行世界线深度推演，请在日志面板查看...)</i></span>"
                await websocket.send_json({"action": "sys_bubble_lock", "html": bubble_html})

                print(f"\n📖 [命运推演]: 正在演算未来的可能性... {desc_text}")
                full_reply = ""

                                                     
                for chunk in llm_brain.stream_story_with_romasha(level, choice_text):
                    if state["cancel_flag"]: return
                    full_reply += chunk

                                          
                    tags = re.findall(r'\[(.*?)\]', full_reply)
                    for tag in tags:
                        tag_lower = tag.lower()
                        if tag_lower not in state["processed_tags"]:
                            state["processed_tags"].add(tag_lower)
                            if tag_lower.startswith(('act_', 'mood_', 'wear_', 'hair_')):
                                await execute_tag(websocket, tag_lower, state)

                                    
                    await websocket.send_json({"action": "story_chunk", "text": chunk})
                    await asyncio.sleep(0.02)              

                                     
                                                            
                                       
                                                            
                if "[sys_chapter_up]" in full_reply.lower():
                    current_ch = llm_brain.config.get("current_chapter", 1)
                    if current_ch < 5:              
                        llm_brain.config["current_chapter"] = current_ch + 1
                        llm_brain.save_config()
                        print(f"\n🌌 [命运回响]: 剧本弧光完成，命运齿轮转动，已自动推进至【第  {current_ch + 1}  章】的推演节点。")

                                          
                        await websocket.send_json({
                            "action": "sys_bubble",
                            "html": f"<span style='color:#6031e2; font-weight:bold; font-size: var(--main-font-size);'>🌌 命运的齿轮转动，已自动进入第 {current_ch + 1} 阶段...</span>",
                            "duration": 5000
                        })
                                                                
                      
                options_match = re.search(r'[<＜]\s*options\s*[>＞](.*?)([<＜]/\s*options\s*[>＞]|$)', full_reply,
                                              flags=re.DOTALL | re.IGNORECASE)
                pending_story_options = []
                options_raw = ""
                fallback_match = None

                if options_match:
                    options_raw = options_match.group(1).strip()
                else:
                                                                        
                    fallback_match = re.search(r'(1\.\s*.*)$', full_reply, re.DOTALL)
                    if fallback_match:
                        options_raw = fallback_match.group(1).strip()
                        options_raw = re.sub(r'[<＜]/?\s*options\s*[>＞]?', '', options_raw, flags=re.IGNORECASE).strip()

                if options_raw:
                    if re.search(r'\d+\.', options_raw):
                        opts = re.split(r'\d+\.\s*', options_raw)
                    elif re.search(r'[-*]\s+', options_raw):
                        opts = re.split(r'[-*]\s+', options_raw)
                    else:
                        opts = options_raw.split('\n')
                    pending_story_options = [opt.strip() for opt in opts if opt.strip()]

                                                                
                                               
                    if not pending_story_options:
                        pending_story_options = ["(顺应局势，看看会发生什么...)", "(尝试打破僵局)", "(保持沉默)"]

                           
                display_text = re.sub(r'[<＜]\s*options\s*[>＞].*?([<＜]/\s*options\s*[>＞]|$)', '', full_reply,
                                        flags=re.DOTALL | re.IGNORECASE)

                                                            
                if not options_match and fallback_match:
                    display_text = display_text.replace(fallback_match.group(1), "").strip()

                                                            
                    display_text = re.sub(
                        r'\[(act_|mood_|wear_|hair_|sys_chapter_up|move_to_|set_name_|intimacy_).*?\]', '',
                        display_text, flags=re.IGNORECASE)
                    display_text = display_text.replace("[sys_chapter_up]", "")             

                                                      
                say_matches = re.findall(r'\[say:\s*"(.*?)"\]', full_reply, re.DOTALL)
                tts_text = "。".join(say_matches).strip()

                                                 
                display_text = re.sub(r'\[say:\s*"[^"]*?<\|endofprompt\|>(.*?)"\]', r'“\1”', display_text,
                                      flags=re.DOTALL)
                display_text = re.sub(r'\[say:\s*"(.*?)"\]', r'“\1”', display_text, flags=re.DOTALL)

                             
                display_text = re.sub(r'\[.*?\]', '', display_text).strip()

                                   
                novel_path = os.path.join("world_data", "novel_log.txt")
                os.makedirs(os.path.dirname(novel_path), exist_ok=True)
                with open(novel_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n--- 【推演节点记录: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}】 ---\n")
                    f.write(display_text)

                                       
                await websocket.send_json({
                    "action": "story_text_update",
                    "final_text": display_text
                })

                                     
                state["pending_story_options"] = pending_story_options

                             
                if tts_text:
                                   
                    clean_tts_print = re.sub(r'^.*?<\|endofprompt\|>', '', tts_text)
                    clean_tts_print = re.sub(r'\[.*?\]', '', clean_tts_print).strip()
                    print(f"\n🗣️ [剧情高光台词]: {clean_tts_print}")
                    bubble_html = f"<span style='color:#fd92a1; font-weight:bold; font-size: var(--main-font-size);'>「{clean_tts_print}」</span><br>"

                    if voice_enabled:
                        state["audio_start_event"].clear()
                        audio_base64, success, status = await process_tts(tts_text)

                        if state["cancel_flag"]: return

                                                   
                        if state["thought_id_counter"] != my_thought_id:
                            print("👻 [系统拦截]: 捕获到上一轮的幽灵剧情语音，已将其销毁！")
                            return

                        if success and audio_base64:
                            await websocket.send_json({"action": "play_audio", "url": audio_base64})
                            await websocket.send_json({"action": "bubble", "html": bubble_html})

                            try:
                                await asyncio.wait_for(state["audio_start_event"].wait(), timeout=30.0)
                            except asyncio.TimeoutError:
                                pass
                        else:
                                                                         
                            print("\n⚠️ [感官适应]: 语音服务无响应，已自动关闭语音生成。")
                            llm_brain.config["voice_enabled"] = False
                            llm_brain.save_config()
                            await websocket.send_json({"action": "sync_config", "voice_enabled": False})

                                              
                            await websocket.send_json({"action": "bubble", "html": bubble_html})
                            await asyncio.sleep(2.0)
                            if state["thought_id_counter"] == my_thought_id:
                                await on_speech_finished()
                    else:
                                           
                        await websocket.send_json({"action": "bubble", "html": bubble_html})
                        await asyncio.sleep(2.0)
                        if state["thought_id_counter"] == my_thought_id:
                            await on_speech_finished()
                else:
                    await asyncio.sleep(2.0)
                    if state["thought_id_counter"] == my_thought_id:
                        await on_speech_finished()

            finally:
                state["is_generating"] = False

    def reset_afk():
                                 
        was_deep_sleeping = (state["vision_idle_seconds"] >= 300)

        state["thought_idle_seconds"] = 0
        state["vision_idle_seconds"] = 0
        state["vision_sleep_count"] = 0
        state["next_idle_trigger_minutes"] = 3
        state["current_idle_target_seconds"] = 180
        if state["is_tracking"]:
            asyncio.create_task(websocket.send_json({"action": "tracking", "state": True}))
                
                                                  
        if was_deep_sleeping:
            asyncio.create_task(
                websocket.send_json({"action": "idle_motion", "group": "BaseMotions", "index": state["current_idle_motion"]}))

    touch_prompts = {
        "head": "*你温柔地摸了摸她的头*", "face": "*你轻轻戳了戳她的脸颊*", "bust": "*你不小心碰到了她的胸部*",
        "belly": "*你搂住了她的腰*", "hip": "*你不小心碰到了她的臀部*", "crotch": "*你不小心碰到了她的隐私部位*",
        "leg": "*你碰到了她的腿*", "hand_right": "*你牵起了她的右手*", "hand_left": "*你握住了她的左手*",
        "unknown": "*你轻轻碰了碰她*"
    }

    heartbeat_task = asyncio.create_task(heartbeat_engine())

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            msg_type = payload.get("type", "")

            if msg_type == "system" and payload.get("text") == "EVENT:READY":
                await check_and_apply_outfit(websocket, is_initial=True)

                                              
                if llm_brain.config.get("is_first_encounter", True) and llm_brain.config.get("current_chapter", 1) == 1:
                    intro_text = "故事刚刚开始：她刚刚击败龙人少女，又遭遇了迪亚德的羞辱与监控，正一个人在房间里心力交瘁、极度迷茫……(试着对她搭话来开启命运的齿轮吧)"
                    print(f"\n🌟 [命运指引]: {intro_text}")

                                           
                    async def send_intro_bubble():
                        await asyncio.sleep(2)
                        await websocket.send_json({
                            "action": "sys_bubble",
                            "html": f"<span style='color:#6031e2; font-weight:bold; font-size: var(--sub-font-size);'>🌟 {intro_text}</span>",
                            "duration": 10000                   
                        })

                    asyncio.create_task(send_intro_bubble())
                          

                continue

            if msg_type == "system" and payload.get("text") == "EVENT:AUDIO_END":
                             
                await on_speech_finished()
                continue

                                               
            if msg_type == "system" and payload.get("text") == "EVENT:AUDIO_START":
                state["audio_start_event"].set()
                continue

                                                  
                                                               
                                                  
                         

            if msg_type == "drag":
                state["vision_idle_seconds"] = 0
                if state["is_tracking"]:
                    await websocket.send_json({"action": "tracking", "state": True})
                continue

            reset_afk()
            user_text = ""

            if msg_type == "track_cmd":
                state["is_tracking"] = payload.get("state", True)

                                          
                llm_brain.config["track_enabled"] = state["is_tracking"]
                llm_brain.save_config()

                         
                action_desc = "重新锁定了你的身影" if state["is_tracking"] else "不再追随你的动作"
                print(f"\n👁️ [空间感知]: Romasha的视线{action_desc}。")
                await websocket.send_json({"action": "tracking", "state": state["is_tracking"]})
                         
                bubble_desc = "她似乎注意到了你在这边..." if state["is_tracking"] else "她移开了视线，不再关注你的举动..."
                await websocket.send_json({"action": "sys_bubble",
                                           "html": f"<span style='color:#888; font-size: var(--sub-font-size);'><i>({bubble_desc})</i></span>"})
                continue

                               
            if msg_type == "touch_cmd":
                state_bool = payload.get("state", True)

                                          
                llm_brain.config["touch_enabled"] = state_bool
                llm_brain.save_config()

                action_desc = "仿佛重新建立起了真实的触感，能感受到彼此的温度" if state_bool else "之间仿佛隔了一层不可触及的空气墙"
                print(f"\n👆 [无声羁绊]: 你们{action_desc}。")
                bubble_desc = "她似乎能真切感受到你的存在..." if state_bool else "触碰的感知似乎被隔绝了..."
                await websocket.send_json({"action": "sys_bubble",
                                           "html": f"<span style='color:#888; font-size: var(--sub-font-size);'><i>({bubble_desc})</i></span>"})
                continue

                                           
            interrupted_text = ""
            if msg_type in ["chat", "touch"]:
                state["thought_id_counter"] += 1              

                                                 
                await websocket.send_json({"action": "stop_audio"})

                if state["is_generating"]:
                    state["cancel_flag"] = True
                    clean_accumulated = re.sub(r'\[.*?\]', '', state["accumulated_text"]).strip()
                    if len(clean_accumulated) > 2:
                        interrupted_text = clean_accumulated
                                             
                    await asyncio.sleep(0.05)

                         
            if msg_type == "voice_cmd":
                user_text = payload.get("text", "")
                val = user_text.split(' ')[1].strip().lower()
                bubble_desc = ""
                if val in ["0", "1"]:
                    state_bool = val == "1"
                    llm_brain.config["voice_enabled"] = state_bool
                    llm_brain.save_config()
                    if state_bool:
                        print(f"\n💭 [感官羁绊]: 周围安静了下来，你终于又能听见她清晰的声音了。")
                        bubble_desc = "你靠近了一些，试着倾听她的声音..."
                    else:
                        print(f"\n💭 [感官羁绊]: 环境变得嘈杂，你只能通过她的眼神和口型来理解她。")
                        bubble_desc = "周围有些吵闹，你默默注视着她..."
                elif val in ["cosyvoice", "sovits"]:
                    llm_brain.config["tts_engine"] = val
                    llm_brain.config["voice_enabled"] = True
                    llm_brain.save_config()
                    print(f"\n💭 [灵魂调律]: 冥冥之中，她发声的方式与声线中蕴含的温度，似乎发生了极其微妙的改变。")
                    bubble_desc = f"一阵轻微的恍惚后，她的声音听起来似乎有些不同了：{val}..."

                if bubble_desc:
                    await websocket.send_json({"action": "sys_bubble",
                                                   "html": f"<span style='color:#888; font-size: var(--sub-font-size);'><i>({bubble_desc})</i></span>"})
                continue

                         
            if msg_type == "terminal_cmd":
                state_bool = payload.get("state", True)
                is_init = payload.get("init", False)               
                                                           
                bubble_desc = "已开启底层终端视觉..." if state_bool else "已关闭底层终端视觉..."

                                               
                if not is_init:
                    await websocket.send_json({"action": "sys_bubble",
                                                "html": f"<span style='color:#888; font-size: var(--sub-font-size);'><i>({bubble_desc})</i></span>"})
                continue

            if msg_type == "size_cmd":
                size_val = payload.get("val", 1)
                llm_brain.config["bubble_size"] = size_val
                llm_brain.save_config()

                                              
                size_desc = ['稍微拉远', '恰到好处', '更加贴近'][size_val]
                print(f"\n📏 [认知焦距]: 伴随着你注意力的集中，眼前的思绪与话语变得{size_desc}了。")
                bubble_html = f"<span style='color:#888; font-size: var(--sub-font-size);'><i>(视界已调整为适宜的大小...)</i></span>"
                await websocket.send_json({"action": "sys_bubble", "html": bubble_html})
                continue

                        
            if msg_type == "ja_cmd":
                state_bool = payload.get("state", True)
                llm_brain.config["tts_translate_to_ja"] = state_bool
                llm_brain.save_config()

                if state_bool:
                    print(f"\n🌐 [语言中枢]: 她的发声回路切换为了古老的异国语调 (日语翻译已开启)。")
                    bubble_desc = "她的口型似乎在尝试一种古老而优雅的发音..."
                else:
                    print(f"\n🌐 [语言中枢]: 她的发声回路恢复了你所熟悉的语言 (日语翻译已关闭)。")
                    bubble_desc = "她的语调恢复了正常的频率..."

                bubble_html = f"<span style='color:#888; font-size: var(--sub-font-size);'><i>({bubble_desc})</i></span>"
                await websocket.send_json({"action": "sys_bubble", "html": bubble_html})
                continue

            if msg_type == "chat":
                user_text = payload.get("text", "")

                                                         
                if user_text.startswith("[set_name_") and user_text.endswith("]"):
                    new_name = user_text[10:-1].strip()
                    if new_name:
                        llm_brain.config["player_name"] = new_name
                        llm_brain.save_config()
                        print(f"\n📝 [羁绊铭记]: 已将你的称呼更新为：{new_name}")
                    continue                       

                        
                if user_text.startswith('/chapter '):
                    try:
                        ch_num = int(user_text.split(' ')[1])
                        if 1 <= ch_num <= 10:
                            llm_brain.config["current_chapter"] = ch_num
                            llm_brain.save_config()

                            print(f"\n📖 [命运流转]: 世界的齿轮已拨动，当前推演时间线跃迁至：第 {ch_num} 章。")
                            bubble_desc = f"时间的刻度跳动了，你们来到了新的阶段 (第 {ch_num} 章)..."

                                            
                            state["thought_id_counter"] += 1
                            if state["is_generating"]:
                                state["cancel_flag"] = True
                                await websocket.send_json({"action": "stop_audio"})
                                await asyncio.sleep(0.05)

                            await websocket.send_json({"action": "sys_bubble",
                                                        "html": f"<span style='color:#6031e2; font-size: var(--sub-font-size);'><i>({bubble_desc})</i></span>",
                                                        "duration": 4000})
                        continue                                                      
                    except ValueError:
                        pass

                                 
                if user_text == "/choice /EXIT_STORY_MODE":
                    state["thought_id_counter"] += 1
                    state["is_story_mode"] = False

                                                       
                    state["cancel_flag"] = True
                    state["pending_story_options"] = []
                    await websocket.send_json({"action": "stop_audio"})
                                               
                    await websocket.send_json({"action": "sys_bubble_unlock"})
                    await websocket.send_json({"action": "sys_bubble",
                                               "html": "<span style='color:#e74c3c; font-size: var(--sub-font-size);'><i>(命运观测终端已关闭，切回日常模式...)</i></span>", "duration": 3000})
                    continue

                if user_text == "/choice /CANCEL_GENERATION":
                    state["cancel_flag"] = True
                                          
                    await websocket.send_json({"action": "story_chunk",
                                               "text": "<br><br><span style='color:#e74c3c;'><b>[系统]: ⚠️ 推演已被手动强行中止。你可以直接在下方做出抉择。</b></span><br>"})
                    await websocket.send_json({"action": "stop_audio"})             
                    continue

                if user_text.startswith("/auto "):
                    level = user_text.split(" ")[1].strip()
                    if level in ["0", "1", "2", "3"]:
                        state["is_story_mode"] = True
                        state["story_level"] = level
                        state["thought_id_counter"] += 1

                                                                
                        state["cancel_flag"] = True
                        await websocket.send_json({"action": "stop_audio"})

                                                                           
                        llm_brain.chat_history = [msg for msg in llm_brain.chat_history if
                                                  not msg.get("content", "").startswith("[系统机制")]
                        await websocket.send_json({"action": "sys_bubble",
                                                   "html": f"<span style='color:#6031e2; font-size: var(--sub-font-size);'><i>(已切入世界线推演模式，参与度: {level}...)</i></span>",
                                                   "duration": 3000})                
                                                      
                        await asyncio.sleep(0.1)
                                  
                        asyncio.create_task(trigger_story_thought(level, "", state["thought_id_counter"]))
                    continue

                if user_text.startswith("/choice ") and state.get("is_story_mode", False):
                    choice_text = user_text.replace("/choice ", "").strip()
                    state["thought_id_counter"] += 1

                                                             
                    state["cancel_flag"] = True
                    await websocket.send_json({"action": "stop_audio"})

                                              
                    llm_brain.chat_history = [msg for msg in llm_brain.chat_history if
                                              not msg.get("content", "").startswith("[系统机制")]
                    await websocket.send_json({"action": "sys_bubble",
                                               "html": "<span style='color:#6031e2; font-size: var(--sub-font-size);'><i>(正在推演下个阶段的未来...)</i></span>",
                                               "duration": 4000})                
                    await asyncio.sleep(0.1)
                    asyncio.create_task(
                        trigger_story_thought(state["story_level"], choice_text, state["thought_id_counter"]))
                    continue

                                                
                if user_text == "/SYSTEM_RESET_MEMORY":
                                                           
                    state["thought_id_counter"] += 1
                    if state["is_generating"]:
                        state["cancel_flag"] = True
                        await websocket.send_json({"action": "stop_audio"})
                        await asyncio.sleep(0.05)                

                    memory_manager.clear_all_memories()
                                  
                    story_manager.clear_summary()
                                           
                    lorebook_manager.clear_dynamic_lore()
                                                
                    story_manager.archive_novel_log()
                    llm_brain.chat_history.clear()
                    llm_brain.config["intimacy"] = 0
                    llm_brain.config["player_name"] = ""                      
                                               
                    llm_brain.config["current_location"] = "罗玛莎的房间门口"
                    llm_brain.config["current_chapter"] = 1
                    llm_brain.config["is_first_encounter"] = True                          
                    llm_brain.save_config()
                    print("💔 [记忆消散]: 曾经相处的点滴如沙般流逝，你们回到了最初相遇时的陌生与戒备。\n")

                                              
                    await websocket.send_json({"action": "clear_name_cache"})

                                                    
                    state["current_context_html"] = ""
                    state["accumulated_text"] = ""

                                     
                    await websocket.send_json({"action": "param", "id": "ParamCheek", "value": -99})
                    await websocket.send_json({"action": "param", "id": "angry", "value": -99})
                    state["current_idle_motion"] = motion_manager.get_motion_index('talk')
                    await websocket.send_json(
                        {"action": "idle_motion", "group": "BaseMotions", "index": state["current_idle_motion"]})

                                                                 
                                                             
                    await websocket.send_json({"action": "sys_bubble",
                                               "html": "<span style='color:#888; font-size: var(--sub-font-size);'><i>(记忆已被重置，迎来了崭新的初见...)</i></span>"})
                    app.state.current_time_period = "unknown"
                    await check_and_apply_outfit(websocket, is_initial=True)
                    continue                          

                                                            
                                 
                                                            
                state["thought_id_counter"] += 1
                await websocket.send_json({"action": "stop_audio"})

                if state["is_generating"]:
                    state["cancel_flag"] = True
                    clean_accumulated = re.sub(r'\[.*?\]', '', state["accumulated_text"]).strip()
                    if len(clean_accumulated) > 2:
                        interrupted_text = clean_accumulated
                    await asyncio.sleep(0.05)

                state["current_context_html"] = f"<span style='color:#48a1fa;'>你: {user_text}</span><br>"
                bubble_html = state[
                                    "current_context_html"] + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(她倾听着你的话语...)</i></span>"
                await websocket.send_json({"action": "bubble", "html": bubble_html})

            elif msg_type == "touch":
                part = payload.get("part", "unknown")
                user_text = touch_prompts.get(part, "*你触碰了她*")
                state["current_context_html"] = f"<span style='color:#fd92a1;'>{user_text}</span><br>"
                bubble_html = state[
                                    "current_context_html"] + "<span style='color:#888; font-size: var(--sub-font-size);'><i>(感受中...)</i></span>"
                await websocket.send_json({"action": "bubble", "html": bubble_html})

            if not user_text:
                continue



                                    
                                                         
            asyncio.create_task(trigger_thought(user_text, state["current_context_html"], False, interrupted_text, state["thought_id_counter"]))

    except WebSocketDisconnect:
        print("\n❌ 手机客户端连接已断开。")
                                                                  
        connected_clients.discard(websocket)                            
        print("💾 [羁绊铭记]: 你们之间的距离与视角，已默默留存在了记忆中，期待下次相遇。")               
        state["cancel_flag"] = True                                       
    except Exception as e:
        print(f"\n⚠️ WebSocket 异常: {e}")
    finally:
        heartbeat_task.cancel()


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)