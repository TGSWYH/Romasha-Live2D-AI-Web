                   
                                                              
                  
                                                              
            
                                    
                           
                                         
                                                              
import io
import time
import base64
import hashlib
import asyncio
import threading
from typing import Optional, Callable

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TemporalFrameBuffer:


    def __init__(self, max_age_seconds=180):
        self.frames = []                                                   
        self.max_age_seconds = max_age_seconds
        self._lock = threading.Lock()

    def add_frame(self, image_b64, hash_val, raw_size=None):
        now = time.time()
        with self._lock:
            change_score = self._compute_change_score(hash_val)
            self.frames.append({
                'image_b64': image_b64,
                'ts': now,
                'hash': hash_val,
                'change_score': change_score,
                'raw_size': raw_size
            })
            cutoff = now - self.max_age_seconds
            self.frames = [f for f in self.frames if f['ts'] > cutoff]
        return change_score

    def _compute_change_score(self, new_hash):
        if not self.frames or not new_hash:
            return 1.0
        last_hash = self.frames[-1].get('hash')
        if not last_hash:
            return 0.5
        try:
            xor_int = int(new_hash, 16) ^ int(last_hash, 16)
            diff_bits = bin(xor_int).count('1')
            total_bits = len(new_hash) * 4
            return diff_bits / total_bits if total_bits else 0.0
        except Exception:
            return 0.5

    def get_recent_max_change(self, window_seconds=15):
        with self._lock:
            now = time.time()
            recent = [f for f in self.frames if now - f['ts'] < window_seconds]
            if not recent:
                return 0.0
            return max(f['change_score'] for f in recent)

    def get_context_frames(self, target_offsets=(0, 5, 20, 60)):

        with self._lock:
            if not self.frames:
                return []
            now = time.time()
            picked = []
            picked_ts = set()
            for offset in target_offsets:
                target_ts = now - offset
                closest = min(self.frames, key=lambda f: abs(f['ts'] - target_ts))
                if closest['ts'] not in picked_ts:
                    picked.append((closest, max(0, int(now - closest['ts']))))
                    picked_ts.add(closest['ts'])
            picked.sort(key=lambda x: -x[1])
            return picked

    def get_latest(self):
        with self._lock:
            return self.frames[-1] if self.frames else None

    def clear(self):
        with self._lock:
            self.frames.clear()

    def is_empty(self):
        with self._lock:
            return len(self.frames) == 0


class VisionManager:










    def __init__(self, config):
        self.config = config

              
        self.screen_enabled = False
        self.front_camera_enabled = False
        self.back_camera_enabled = False

                
        max_age = int(self.config.get("vision_buffer_max_age", 180))
        self.screen_buffer = TemporalFrameBuffer(max_age_seconds=max_age)
        self.front_camera_buffer = TemporalFrameBuffer(max_age_seconds=max_age)
        self.back_camera_buffer = TemporalFrameBuffer(max_age_seconds=max_age)

                          
        self.on_scene_change: Optional[Callable] = None

                      
        self.main_api_vision_capable = self._read_main_api_vision_flag()

    def _read_main_api_vision_flag(self):
        v = str(self.config.get("main_api_supports_vision", "auto")).lower()
        if v == "true":
            return True
        if v == "false":
            return False
        return None

                                                                  
                                  
                                                                  
    def set_vision_mode(self, mode):

        try:
            mode = int(mode)
        except Exception:
            mode = 0

        new_screen = mode in (1, 3)
        new_camera_any = mode in (2, 3)

                              
        self.screen_enabled = new_screen

                                          
        if new_camera_any:
            self._apply_camera_mode(self.config.get("camera_mode", 1))
        else:
            self.front_camera_enabled = False
            self.back_camera_enabled = False

        self.config["vision_mode"] = mode
        self.config["vision_enabled"] = bool(mode)

                            
        if not self.screen_enabled:
            self.screen_buffer.clear()
        if not self.front_camera_enabled:
            self.front_camera_buffer.clear()
        if not self.back_camera_enabled:
            self.back_camera_buffer.clear()

                                                                  
                                      
                                                                  
    def set_camera_mode(self, mode):

        try:
            mode = int(mode)
        except Exception:
            mode = 1
        if mode not in (1, 2, 3):
            mode = 1

        self.config["camera_mode"] = mode

                                     
        if self.config.get("vision_mode", 0) in (2, 3):
            self._apply_camera_mode(mode)

    def _apply_camera_mode(self, mode):
        new_front = mode in (1, 3)
        new_back = mode in (2, 3)

        if not new_front and self.front_camera_enabled:
            self.front_camera_buffer.clear()
        if not new_back and self.back_camera_enabled:
            self.back_camera_buffer.clear()

        self.front_camera_enabled = new_front
        self.back_camera_enabled = new_back

    def has_active_sensors(self):
        return (self.screen_enabled or
                self.front_camera_enabled or
                self.back_camera_enabled)

                                                                  
              
                                                                  
                            
                                                                  
    async def ingest_frame(self, source: str, image_b64: str):




        if not image_b64:
            return

              
        try:
            raw = base64.b64decode(image_b64[:8192] + "==")                
            hash_val = hashlib.md5(raw).hexdigest()
        except Exception:
            hash_val = hashlib.md5(image_b64[:1024].encode()).hexdigest()

        buffer = None
        if source == "screen" and self.screen_enabled:
            buffer = self.screen_buffer
        elif source == "front_camera" and self.front_camera_enabled:
            buffer = self.front_camera_buffer
        elif source == "back_camera" and self.back_camera_enabled:
            buffer = self.back_camera_buffer

        if buffer is None:
            return             

        change_score = buffer.add_frame(image_b64, hash_val)

                     
        major_thresh = float(self.config.get("vision_major_change_threshold", 0.30))
        if change_score >= major_thresh and self.on_scene_change:
            try:
                await self.on_scene_change(source, change_score)
            except Exception as e:
                print(f"⚠️ [视觉感知] 场景变化回调失败: {e}")

                                                                  
                          
                                                                  
    def build_multimodal_parts(self, time_offsets=None,
                               temporary_screen=False,
                               temporary_front_camera=False,
                               temporary_back_camera=False):







        if time_offsets is None:
            time_offsets = tuple(self.config.get(
                "vision_context_offsets", [0, 5, 20, 60]
            ))

        parts = []
        latest_history_size = int(self.config.get("vision_history_max_size", 768))
        latest_now_size = int(self.config.get("vision_max_size", 1280))

                                                                
             
                                                                
        include_screen = self.screen_enabled or temporary_screen
        if include_screen and not self.screen_buffer.is_empty():
            self._append_buffer_frames(
                parts, self.screen_buffer, time_offsets,
                "屏幕画面", "屏幕"
            )
            stable_hint = self._build_stability_hint(self.screen_buffer, "屏幕")
            if stable_hint:
                parts.append({"type": "text", "text": stable_hint})

                                                                
                     
                                                                
        include_front = self.front_camera_enabled or temporary_front_camera
        if include_front and not self.front_camera_buffer.is_empty():
            self._append_buffer_frames(
                parts, self.front_camera_buffer, time_offsets,
                "前置摄像头画面 - 玩家本人", "前置摄像头"
            )

                                                                
                         
                                                                
        include_back = self.back_camera_enabled or temporary_back_camera
        if include_back and not self.back_camera_buffer.is_empty():
            self._append_buffer_frames(
                parts, self.back_camera_buffer, time_offsets,
                "后置摄像头画面 - 玩家正面对的环境", "后置摄像头"
            )

                                                                
                      
                                                                
        if parts:
            parts.insert(0, {
                "type": "text",
                "text": ("（以下是你此刻通过视觉真实看到的多帧画面,按时间从老到新排列。"
                         "请像真实的人那样自然反应,不要描述这是图片或截图,要把它当作你眼睛真的看到的世界。"
                         "如果同时有屏幕和摄像头画面,请理解屏幕是玩家正在用的设备界面,摄像头反映的是玩家本人或他面对的环境。）")
            })

        return parts

    def _append_buffer_frames(self, parts, buffer, time_offsets, label_prefix, short_label):

        frames = buffer.get_context_frames(time_offsets)
        for i, (frame, age) in enumerate(frames):
            is_now = (i == len(frames) - 1)
            age_label = self._format_age_label(age)
            parts.append({
                "type": "text",
                "text": f"【{label_prefix} - {age_label}】"
            })
            b64 = frame['image_b64']
            detail = "high" if is_now else "low"
            parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": detail
                }
            })

    def _format_age_label(self, age_seconds):
        if age_seconds < 2:
            return "现在"
        elif age_seconds < 60:
            return f"{age_seconds}秒前"
        elif age_seconds < 3600:
            return f"约{age_seconds // 60}分钟前"
        else:
            return f"约{age_seconds // 3600}小时前"

    def _build_stability_hint(self, buffer, name="画面"):
        recent_max = buffer.get_recent_max_change(window_seconds=30)
        if recent_max < 0.05:
            return f"（环境提示:最近30秒内{name}几乎没有明显变化,玩家可能保持着同一个状态。）"
        elif recent_max > 0.4:
            return f"（环境提示:最近30秒内{name}发生过明显变化(变化峰值{int(recent_max * 100)}%),很可能切换了内容或场景。）"
        return None

                                                                  
                               
                                                                  
    def get_recent_change_level(self, window_seconds=20):
        s = self.screen_buffer.get_recent_max_change(window_seconds) if self.screen_enabled else 0.0
        f = self.front_camera_buffer.get_recent_max_change(window_seconds) if self.front_camera_enabled else 0.0
        b = self.back_camera_buffer.get_recent_max_change(window_seconds) if self.back_camera_enabled else 0.0
        return max(s, f, b)