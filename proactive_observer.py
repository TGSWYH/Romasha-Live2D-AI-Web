                       
                                                              
                       
                                                              
          
                                       
                             
                                                              
import time
import random
import asyncio
from typing import Optional, Callable


class ProactiveObserver:




                                                                  
                       
                                        
                                     
                                      
                                                                  
    SENSITIVITY_PROFILES = {
                        
        "low": {
            "min_interval": 120,                 
            "after_user_cooldown": 180,                  
            "after_ai_cooldown": 180,                 
            "scene_major_thresh": 0.55,                       
            "scene_moderate_thresh": 0.40,             
            "audio_event_thresh": 0.75,               
            "periodic_silence": 900,                   
            "periodic_probability": 0.10,                 
            "scene_moderate_probability": 0.15,
        },
                               
        "mid": {
            "min_interval": 60,
            "after_user_cooldown": 90,
            "after_ai_cooldown": 90,
            "scene_major_thresh": 0.40,
            "scene_moderate_thresh": 0.25,
            "audio_event_thresh": 0.6,
            "periodic_silence": 300,        
            "periodic_probability": 0.20,
            "scene_moderate_probability": 0.35,
        },
                                  
        "high": {
            "min_interval": 35,
            "after_user_cooldown": 50,
            "after_ai_cooldown": 60,
            "scene_major_thresh": 0.30,
            "scene_moderate_thresh": 0.18,
            "audio_event_thresh": 0.5,
            "periodic_silence": 180,
            "periodic_probability": 0.35,
            "scene_moderate_probability": 0.55,
        }
    }

    def __init__(self, config, vision_manager, audio_manager):
        self.config = config
        self.vm = vision_manager
        self.am = audio_manager

        self.last_trigger_time = 0
        self.last_user_input_time = 0
        self.last_ai_speak_time = 0

                                  
        self._extra_blockers: list = []

        self._task = None
        self._running = False

        self._set_sensitivity(self.config.get("sensor_sensitivity", "mid"))

                                
        self.on_proactive_trigger: Optional[Callable] = None

                              
        if self.vm:
            self.vm.on_scene_change = self._on_scene_change
        if self.am:
            self.am.on_mic_speech_detected = self._on_user_voice
            self.am.on_audio_event = self._on_audio_event

    def _set_sensitivity(self, level):
        profile = self.SENSITIVITY_PROFILES.get(level, self.SENSITIVITY_PROFILES["mid"])
        self.profile = profile
        self.config["sensor_sensitivity"] = level

    def set_sensitivity(self, level):
        if level in self.SENSITIVITY_PROFILES:
            self._set_sensitivity(level)
            return True
        return False

                                                                  
            
                                                                  
    def notify_user_input(self):
        self.last_user_input_time = time.time()

    def notify_ai_speak(self):
        self.last_ai_speak_time = time.time()

    def add_blocker(self, blocker_fn: Callable[[], bool]):

        self._extra_blockers.append(blocker_fn)

    async def _on_user_voice(self):
        self.last_user_input_time = time.time()

                                                                  
        
                                                                  
    def start(self, loop):
        if self._running:
            return
        self._running = True
        self._task = asyncio.run_coroutine_threadsafe(self._loop(), loop) \
            if not asyncio.get_event_loop().is_running() else \
            asyncio.create_task(self._loop())

    def stop(self):
        self._running = False
        if self._task:
            try:
                self._task.cancel()
            except Exception:
                pass

                                                                  
          
                                                                  
    def _has_active_sensors(self):
        v_active = self.vm and self.vm.has_active_sensors()
        a_active = self.am and self.am.has_active_sensors()
        return v_active or a_active

    def _can_trigger(self):
        if not self.config.get("proactive_enabled", True):
            return False
        if not self._has_active_sensors():
            return False
        for blocker in self._extra_blockers:
            try:
                if blocker():
                    return False
            except Exception:
                pass

        now = time.time()
        if now - self.last_trigger_time < self.profile["min_interval"]:
            return False
        if now - self.last_user_input_time < self.profile["after_user_cooldown"]:
            return False
        if now - self.last_ai_speak_time < self.profile["after_ai_cooldown"]:
            return False
        return True

                                                                  
          
                                                                  
    async def _on_scene_change(self, source, change_score):
        if not self._can_trigger():
            return

        if change_score >= self.profile["scene_major_thresh"]:
            await self._fire("scene_change_major", {
                "source": source,
                "change_score": change_score
            })
        elif change_score >= self.profile["scene_moderate_thresh"]:
            if random.random() < self.profile["scene_moderate_probability"]:
                await self._fire("scene_change_moderate", {
                    "source": source,
                    "change_score": change_score
                })

    async def _on_audio_event(self, source, intensity):
        if not self._can_trigger():
            return
        if intensity >= self.profile["audio_event_thresh"]:
            await self._fire("audio_event", {
                "source": source,
                "intensity": intensity
            })

    async def _loop(self):
        check_interval = 12
        while self._running:
            try:
                await asyncio.sleep(check_interval)
                if not self._running:
                    break
                await self._tick_periodic()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ [主动观察] 心跳异常: {e}")

    async def _tick_periodic(self):
        if not self._can_trigger():
            return
        now = time.time()
        last_active = max(self.last_user_input_time, self.last_ai_speak_time)
        silence_for = now - last_active if last_active > 0 else 999
        if silence_for < self.profile["periodic_silence"]:
            return
        if random.random() < self.profile["periodic_probability"]:
            await self._fire("periodic_check", {
                "silence_seconds": int(silence_for)
            })

    async def _fire(self, reason, ctx):
        self.last_trigger_time = time.time()
        ctx = dict(ctx) if ctx else {}
        ctx["reason"] = reason
        if self.on_proactive_trigger:
            try:
                await self.on_proactive_trigger(reason, ctx)
            except Exception as e:
                print(f"⚠️ [主动观察] 触发回调失败: {e}")