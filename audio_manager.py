                  
                                                              
            
                                                              
           
                                  
                                           
                               
                                                              
import os
import sys
import time
import asyncio
import threading
import tempfile
from collections import deque
from typing import Optional, Callable


                                                              
                                  
                                                              
def _setup_cuda_dll_paths():
    if sys.platform != "win32":
        return 0
    if not hasattr(os, "add_dll_directory"):
        return 0

    print("🔍 [CUDA路径] 扫描 nvidia DLL 目录...")
    candidates = []
    venv_lib = os.path.join(sys.prefix, "Lib", "site-packages")
    if os.path.isdir(venv_lib):
        candidates.append(venv_lib)
    try:
        import site
        for sp in site.getsitepackages():
            if os.path.isdir(sp) and sp not in candidates:
                candidates.append(sp)
    except Exception:
        pass

    if not candidates:
        return 0

    found_dlls = {}
    added = 0
    seen = set()
    for sp in candidates:
        nvidia_root = os.path.join(sp, "nvidia")
        if not os.path.isdir(nvidia_root):
            continue
        try:
            sub_dirs = sorted(os.listdir(nvidia_root))
        except Exception:
            continue
        for sub in sub_dirs:
            bin_dir = os.path.join(nvidia_root, sub, "bin")
            if not os.path.isdir(bin_dir) or bin_dir in seen:
                continue
            try:
                os.add_dll_directory(bin_dir)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                seen.add(bin_dir)
                added += 1
                try:
                    for d in os.listdir(bin_dir):
                        if d.lower().endswith(".dll"):
                            found_dlls[d.lower()] = bin_dir
                except Exception:
                    pass
            except Exception:
                pass
    return added


_CUDA_DLL_DIRS_REGISTERED = _setup_cuda_dll_paths()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


class AudioManager:










    def __init__(self, config):
        self.config = config

            
        self.mic_enabled = False
        self.sys_enabled = False
        self.mic_mode = self.config.get("mic_mode", "input")                

                 
        self.whisper_model = None
        self._whisper_lock = threading.Lock()
        self._whisper_loading = False
        self._cpu_fallback_attempted = False

                  
        self.sys_transcript_buffer = deque(maxlen=20)

              
        self.on_mic_text_finalized: Optional[Callable] = None
        self.on_sys_text_finalized: Optional[Callable] = None
        self.on_mic_speech_detected: Optional[Callable] = None
        self.on_audio_event: Optional[Callable] = None        

                        
        self.sys_audio_baseline = 0.01
        self.sys_audio_baseline_alpha = 0.05

                                                                  
                  
                                                                  
    def _ensure_whisper_async(self):
        if self.whisper_model is not None or self._whisper_loading:
            return
        self._whisper_loading = True

        def _load():
            if not WHISPER_AVAILABLE:
                print("⚠️ [听觉感知] faster-whisper 未安装")
                self._whisper_loading = False
                return
            size = self.config.get("whisper_model", "small")
            device = self.config.get("whisper_device", "auto")
            compute = self.config.get("whisper_compute", "int8")
            try:
                print(f"🎙️ [听觉感知] 后台加载 Whisper {size} ({device}/{compute})...")
                local_root = os.path.join(APP_DIR, "models", "whisper")
                model = WhisperModel(
                    size, device=device, compute_type=compute,
                    download_root=local_root if os.path.isdir(local_root) else None
                )
                with self._whisper_lock:
                    self.whisper_model = model
                print("🎙️ [听觉感知] Whisper 模型已就绪。")
            except Exception as e:
                print(f"⚠️ [听觉感知] Whisper 加载失败: {e}")
            finally:
                self._whisper_loading = False

        threading.Thread(target=_load, daemon=True).start()

                                                                  
                         
                                                                  
    def _transcribe_sync(self, audio_bytes_or_path):

        if self.whisper_model is None:
            return ""

        lang = self.config.get("whisper_language") or None

                                                
        if isinstance(audio_bytes_or_path, (bytes, bytearray)):
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, dir=os.path.join(APP_DIR, "temp_audio")
            )
            os.makedirs(os.path.dirname(tmp.name), exist_ok=True)
            tmp.write(audio_bytes_or_path)
            tmp.close()
            audio_path = tmp.name
            need_cleanup = True
        else:
            audio_path = audio_bytes_or_path
            need_cleanup = False

        try:
            with self._whisper_lock:
                try:
                    segments, info = self.whisper_model.transcribe(
                        audio_path, language=lang, beam_size=1,
                        vad_filter=True,
                        vad_parameters={"min_silence_duration_ms": 400}
                    )
                    text = "".join(seg.text for seg in segments).strip()
                    return text, info.language if info else lang
                except Exception as e:
                    err_str = str(e).lower()
                    cuda_err = ("cublas" in err_str or "cudnn" in err_str
                                or "cuda" in err_str
                                or "is not found or cannot be loaded" in err_str)
                    if cuda_err and not self._cpu_fallback_attempted:
                        self._cpu_fallback_attempted = True
                        print(f"⚠️ [听觉感知] GPU推理失败,降级到CPU: {e}")
                        try:
                            size = self.config.get("whisper_model", "small")
                            local_root = os.path.join(APP_DIR, "models", "whisper")
                            self.whisper_model = WhisperModel(
                                size, device="cpu", compute_type="int8",
                                download_root=local_root if os.path.isdir(local_root) else None
                            )
                            print("✅ [听觉感知] CPU模式加载成功,重试...")
                            segments, info = self.whisper_model.transcribe(
                                audio_path, language=lang, beam_size=1,
                                vad_filter=True,
                                vad_parameters={"min_silence_duration_ms": 400}
                            )
                            text = "".join(seg.text for seg in segments).strip()
                            return text, info.language if info else lang
                        except Exception as e2:
                            print(f"⚠️ [听觉感知] CPU降级也失败: {e2}")
                            return "", "unknown"
                    print(f"⚠️ [听觉感知] 识别失败: {e}")
                    return "", "unknown"
        finally:
            if need_cleanup:
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

                                                                  
                            
                                                                  
    async def transcribe(self, audio_bytes):




        if not self.whisper_model:
            self._ensure_whisper_async()
                                
            for _ in range(30):
                if self.whisper_model:
                    break
                await asyncio.sleep(0.2)
            if not self.whisper_model:
                return "", "unknown"

        result = await asyncio.to_thread(self._transcribe_sync, audio_bytes)
        if isinstance(result, tuple):
            return result
        return result, "unknown"

                                                                  
               
                                                                  
    async def ingest_mic_audio(self, audio_bytes):



        if not self.mic_enabled:
            return

                       
        if self.on_mic_speech_detected:
            try:
                await self.on_mic_speech_detected()
            except Exception:
                pass

        text, lang = await self.transcribe(audio_bytes)
        if not text:
            return

        if self.on_mic_text_finalized:
            await self.on_mic_text_finalized(text, lang, self.mic_mode)

    async def ingest_sys_audio(self, audio_bytes, intensity=None):




        if not self.sys_enabled:
            return

                  
        if intensity is not None:
            if intensity > self.sys_audio_baseline * 3.5 and intensity > 0.05:
                normalized = min(1.0, intensity / max(self.sys_audio_baseline * 6, 0.001))
                if self.on_audio_event:
                    try:
                        await self.on_audio_event("sys", normalized)
                    except Exception:
                        pass
            self.sys_audio_baseline = (
                    (1 - self.sys_audio_baseline_alpha) * self.sys_audio_baseline
                    + self.sys_audio_baseline_alpha * intensity
            )

        text, lang = await self.transcribe(audio_bytes)
        if not text:
            return

        self.sys_transcript_buffer.append({'text': text, 'ts': time.time()})

        if self.on_sys_text_finalized:
            await self.on_sys_text_finalized(text, lang)

                                                                  
          
                                                                  
    def set_audio_mode(self, mode):
        try:
            mode = int(mode)
        except Exception:
            mode = 0

        new_mic = mode in (1, 3)
        new_sys = mode in (2, 3)

                           
        if new_mic or new_sys:
            self._ensure_whisper_async()

        self.mic_enabled = new_mic
        self.sys_enabled = new_sys
        self.config["audio_mode"] = mode
        self.config["audio_enabled"] = bool(mode)

    def set_mic_mode(self, mode):
        if mode in ("call", "input"):
            self.mic_mode = mode
            self.config["mic_mode"] = mode

    def get_recent_sys_audio_context(self, max_age_s=None):
        if max_age_s is None:
            max_age_s = int(self.config.get("audio_context_max_age", 30))
        now = time.time()
        recent = [
            t['text'] for t in list(self.sys_transcript_buffer)
            if now - t['ts'] < max_age_s
        ]
        return " | ".join(recent)

    def has_active_sensors(self):
        return self.mic_enabled or self.sys_enabled