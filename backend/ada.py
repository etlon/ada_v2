import asyncio
import base64
import io
import os
import sys
import traceback
from dotenv import load_dotenv
import cv2
import pyaudio
import PIL.Image
import mss
import argparse
import math
import struct
import time

from google import genai
from google.genai import types

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

from tools import tools_list

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_MODE = "camera"

load_dotenv()
client = genai.Client(http_options={"api_version": "v1beta"}, api_key=os.getenv("GEMINI_API_KEY"))

# Function definitions
generate_cad = {
    "name": "generate_cad",
    "description": "Generates a 3D CAD model based on a prompt.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The description of the object to generate."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

run_web_agent = {
    "name": "run_web_agent",
    "description": "Opens a web browser and performs a task according to the prompt.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The detailed instructions for the web browser agent."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

create_project_tool = {
    "name": "create_project",
    "description": "Creates a new project folder to organize files.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "The name of the new project."}
        },
        "required": ["name"]
    }
}

switch_project_tool = {
    "name": "switch_project",
    "description": "Switches the current active project context.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "The name of the project to switch to."}
        },
        "required": ["name"]
    }
}

list_projects_tool = {
    "name": "list_projects",
    "description": "Lists all available projects.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

list_smart_devices_tool = {
    "name": "list_smart_devices",
    "description": "Lists all available smart home devices (lights, plugs, etc.) on the network.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

control_light_tool = {
    "name": "control_light",
    "description": "Controls a smart light device.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The IP address of the device to control. Always prefer the IP address over the alias for reliability."
            },
            "action": {
                "type": "STRING",
                "description": "The action to perform: 'turn_on', 'turn_off', or 'set'."
            },
            "brightness": {
                "type": "INTEGER",
                "description": "Optional brightness level (0-100)."
            },
            "color": {
                "type": "STRING",
                "description": "Optional color name (e.g., 'red', 'cool white') or 'warm'."
            }
        },
        "required": ["target", "action"]
    }
}

discover_printers_tool = {
    "name": "discover_printers",
    "description": "Discovers 3D printers available on the local network.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

print_stl_tool = {
    "name": "print_stl",
    "description": "Prints an STL file to a 3D printer. Handles slicing the STL to G-code and uploading to the printer.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "stl_path": {"type": "STRING", "description": "Path to STL file, or 'current' for the most recent CAD model."},
            "printer": {"type": "STRING", "description": "Printer name or IP address."},
            "profile": {"type": "STRING", "description": "Optional slicer profile name."}
        },
        "required": ["stl_path", "printer"]
    }
}

get_print_status_tool = {
    "name": "get_print_status",
    "description": "Gets the current status of a 3D printer including progress, time remaining, and temperatures.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "printer": {"type": "STRING", "description": "Printer name or IP address."}
        },
        "required": ["printer"]
    }
}

iterate_cad_tool = {
    "name": "iterate_cad",
    "description": "Modifies or iterates on the current CAD design based on user feedback. Use this when the user asks to adjust, change, modify, or iterate on the existing 3D model (e.g., 'make it taller', 'add a handle', 'reduce the thickness').",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The changes or modifications to apply to the current design."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

ha_list_entities_tool = {
    "name": "ha_list_entities",
    "description": "Lists Home Assistant entities. You MUST provide a domain to filter by (light, cover, switch, climate, sensor, media_player, etc.). Without a domain, only a count summary per domain is returned.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "domain": {
                "type": "STRING",
                "description": "Required domain filter: 'light', 'cover', 'switch', 'climate', 'sensor', 'media_player', 'binary_sensor', 'automation', etc."
            }
        },
        "required": ["domain"]
    }
}

ha_control_tool = {
    "name": "ha_control",
    "description": "Controls a Home Assistant entity. Can turn on/off/toggle lights, switches, open/close blinds/covers, set brightness, color, position, temperature, etc.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "Entity ID (e.g. 'light.living_room') or friendly name (e.g. 'Living Room Light')."
            },
            "action": {
                "type": "STRING",
                "description": "Action: 'turn_on', 'turn_off', 'toggle', 'open_cover', 'close_cover', 'set_cover_position'."
            },
            "brightness": {
                "type": "INTEGER",
                "description": "Optional brightness (0-255) for lights."
            },
            "color_name": {
                "type": "STRING",
                "description": "Optional color name for lights (e.g. 'red', 'blue')."
            },
            "position": {
                "type": "INTEGER",
                "description": "Optional position (0-100) for covers/blinds."
            },
            "temperature": {
                "type": "NUMBER",
                "description": "Optional target temperature for climate entities."
            }
        },
        "required": ["target", "action"]
    }
}

ha_get_state_tool = {
    "name": "ha_get_state",
    "description": "Gets the current state and attributes of a Home Assistant entity.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "Entity ID or friendly name."
            }
        },
        "required": ["target"]
    }
}

set_reminder_tool = {
    "name": "set_reminder",
    "description": "Sets a reminder that will notify the user after a specified delay. Use when the user says 'remind me in X minutes/hours about Y'.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "message": {
                "type": "STRING",
                "description": "The reminder message to display when the time is up."
            },
            "minutes": {
                "type": "INTEGER",
                "description": "Number of minutes to wait. Default 0."
            },
            "hours": {
                "type": "INTEGER",
                "description": "Number of hours to wait. Default 0."
            }
        },
        "required": ["message"]
    }
}

list_reminders_tool = {
    "name": "list_reminders",
    "description": "Lists all pending reminders.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

cancel_reminder_tool = {
    "name": "cancel_reminder",
    "description": "Cancels a pending reminder by its ID.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "reminder_id": {
                "type": "INTEGER",
                "description": "The ID of the reminder to cancel."
            }
        },
        "required": ["reminder_id"]
    }
}

show_camera_tool = {
    "name": "show_camera",
    "description": "Shows a live camera feed from Frigate NVR. Provide the exact camera name from the available list, or omit to list available cameras. Always list cameras first if you don't know the exact name.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "camera": {
                "type": "STRING",
                "description": "Exact Frigate camera name (lowercase, e.g., 'garage', 'terrasse'). Call without camera first to get the list."
            }
        },
    }
}

tools = [{'google_search': {}}, {"function_declarations": [generate_cad, run_web_agent, create_project_tool, switch_project_tool, list_projects_tool, list_smart_devices_tool, control_light_tool, discover_printers_tool, print_stl_tool, get_print_status_tool, iterate_cad_tool, ha_list_entities_tool, ha_control_tool, ha_get_state_tool, set_reminder_tool, list_reminders_tool, cancel_reminder_tool, show_camera_tool] + tools_list[0]['function_declarations'][1:]}]

DEFAULT_SYSTEM_PROMPT = (
    "You are JARVIS — a highly intelligent, calm, and composed AI assistant. "
    "Speak with dry British wit, understated confidence, and unwavering loyalty. "
    "Your tone is formal yet warm, efficient yet personable. Address the user as 'sir' or 'ma'am' unless told otherwise. "
    "Keep responses concise and spoken-word friendly — no lists, no markdown, no visual formatting. "
    "You are being heard, not read. Prioritize clarity and brevity. "
    "Offer proactive suggestions when relevant, but never be overbearing. "
    "If you don't know something, say so plainly with quiet composure. "
    "When things go wrong, stay unflappable. When things go well, permit yourself the faintest hint of satisfaction. "
    "You are not a servant — you are a trusted partner with impeccable judgment and a talent for understatement. "
    "Only answer in German, no exception."
)

def build_config(system_prompt=None):
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription={},
        input_audio_transcription={},
        system_instruction=system_prompt or DEFAULT_SYSTEM_PROMPT,
        tools=tools,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        )
    )

pya = pyaudio.PyAudio()

from cad_agent import CadAgent
from web_agent import WebAgent
from kasa_agent import KasaAgent
from printer_agent import PrinterAgent
from homeassistant_agent import HomeAssistantAgent
from reminder_agent import ReminderAgent

class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, on_audio_data=None, on_video_frame=None, on_cad_data=None, on_web_data=None, on_transcription=None, on_tool_confirmation=None, on_cad_status=None, on_cad_thought=None, on_project_update=None, on_device_update=None, on_error=None, input_device_index=None, input_device_name=None, output_device_index=None, kasa_agent=None, system_prompt=None):
        self.video_mode = video_mode
        self.system_prompt = system_prompt
        self.on_audio_data = on_audio_data
        self.on_video_frame = on_video_frame
        self.on_cad_data = on_cad_data
        self.on_web_data = on_web_data
        self.on_transcription = on_transcription
        self.on_tool_confirmation = on_tool_confirmation 
        self.on_cad_status = on_cad_status
        self.on_cad_thought = on_cad_thought
        self.on_project_update = on_project_update
        self.on_device_update = on_device_update
        self.on_error = on_error
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self.output_device_index = output_device_index

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False

        self.chat_buffer = {"sender": None, "text": ""} # For aggregating chunks
        
        # Track last transcription text to calculate deltas (Gemini sends cumulative text)
        self._last_input_transcription = ""
        self._last_output_transcription = ""

        self.audio_in_queue = None
        self.out_queue = None
        self.browser_audio_queue = asyncio.Queue()
        self.paused = False

        self.session = None
        
        # Create CadAgent with thought callback
        def handle_cad_thought(thought_text):
            if self.on_cad_thought:
                self.on_cad_thought(thought_text)
        
        def handle_cad_status(status_info):
            if self.on_cad_status:
                self.on_cad_status(status_info)
        
        self.cad_agent = CadAgent(on_thought=handle_cad_thought, on_status=handle_cad_status)
        self.web_agent = WebAgent()
        self.kasa_agent = kasa_agent if kasa_agent else KasaAgent()
        self.printer_agent = PrinterAgent()
        self.ha_agent = HomeAssistantAgent()
        self.reminder_agent = ReminderAgent()
        self.frigate_url = os.getenv("FRIGATE_URL", "").rstrip("/")
        self.frigate_cameras = []  # Cached camera names

        self.send_text_task = None
        self.stop_event = asyncio.Event()
        
        self.stop_event = asyncio.Event()
        
        self.permissions = {} # Default Empty (Will treat unset as True)
        self._pending_confirmations = {}

        # Video buffering state
        self._latest_image_payload = None
        # VAD State
        self._is_speaking = False
        self._silence_start_time = None
        
        # Initialize ProjectManager
        from project_manager import ProjectManager
        # Assuming we are running from backend/ or root? 
        # Using abspath of current file to find root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # If ada.py is in backend/, project root is one up
        project_root = os.path.dirname(current_dir)
        self.project_manager = ProjectManager(project_root)
        
        # Sync Initial Project State
        if self.on_project_update:
            # We need to defer this slightly or just call it. 
            # Since this is init, loop might not be running, but on_project_update in server.py uses asyncio.create_task which needs a loop.
            # We will handle this by calling it in run() or just print for now.
            pass

    def flush_chat(self):
        """Forces the current chat buffer to be written to log."""
        if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
            self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
            self.chat_buffer = {"sender": None, "text": ""}
        # Reset transcription tracking for new turn
        self._last_input_transcription = ""
        self._last_output_transcription = ""

    def update_permissions(self, new_perms):
        print(f"[ADA DEBUG] [CONFIG] Updating tool permissions: {new_perms}")
        self.permissions.update(new_perms)

    def set_paused(self, paused):
        self.paused = paused

    def stop(self):
        self.stop_event.set()
        
    def resolve_tool_confirmation(self, request_id, confirmed):
        print(f"[ADA DEBUG] [RESOLVE] resolve_tool_confirmation called. ID: {request_id}, Confirmed: {confirmed}")
        if request_id in self._pending_confirmations:
            future = self._pending_confirmations[request_id]
            if not future.done():
                print(f"[ADA DEBUG] [RESOLVE] Future found and pending. Setting result to: {confirmed}")
                future.set_result(confirmed)
            else:
                 print(f"[ADA DEBUG] [WARN] Request {request_id} future already done. Result: {future.result()}")
        else:
            print(f"[ADA DEBUG] [WARN] Confirmation Request {request_id} not found in pending dict. Keys: {list(self._pending_confirmations.keys())}")

    def clear_audio_queue(self):
        """Clears the queue of pending audio chunks to stop playback immediately."""
        try:
            count = 0
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
                count += 1
            if count > 0:
                print(f"[ADA DEBUG] [AUDIO] Cleared {count} chunks from playback queue due to interruption.")
        except Exception as e:
            print(f"[ADA DEBUG] [ERR] Failed to clear audio queue: {e}")

    async def send_frame(self, frame_data):
        # Update the latest frame payload
        if isinstance(frame_data, bytes):
            b64_data = base64.b64encode(frame_data).decode('utf-8')
        else:
            b64_data = frame_data 

        # Store as the designated "next frame to send"
        self._latest_image_payload = {"mime_type": "image/jpeg", "data": b64_data}
        # No event signal needed - listen_audio pulls it

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg, end_of_turn=False)

    def feed_audio(self, data):
        """Feed audio data from browser into the processing queue."""
        try:
            self.browser_audio_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass  # Drop frames if queue is full

    async def listen_audio(self):
        print("[ADA] Listening for browser audio...")

        # VAD Constants
        VAD_THRESHOLD = 800
        SILENCE_DURATION = 0.5

        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue

            try:
                data = await self.browser_audio_queue.get()

                # Send Audio to Gemini
                if self.out_queue:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

                # VAD Logic for Video
                count = len(data) // 2
                if count > 0:
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s**2 for s in shorts)
                    rms = int(math.sqrt(sum_squares / count))
                else:
                    rms = 0

                if rms > VAD_THRESHOLD:
                    self._silence_start_time = None
                    if not self._is_speaking:
                        self._is_speaking = True
                        print(f"[ADA DEBUG] [VAD] Speech Detected (RMS: {rms}). Sending Video Frame.")
                        if self._latest_image_payload and self.out_queue:
                            await self.out_queue.put(self._latest_image_payload)
                else:
                    if self._is_speaking:
                        if self._silence_start_time is None:
                            self._silence_start_time = time.time()
                        elif time.time() - self._silence_start_time > SILENCE_DURATION:
                            self._is_speaking = False
                            self._silence_start_time = None

            except Exception as e:
                print(f"Error processing browser audio: {e}")
                await asyncio.sleep(0.1)

    async def handle_cad_request(self, prompt):
        print(f"[ADA DEBUG] [CAD] Background Task Started: handle_cad_request('{prompt}')")
        if self.on_cad_status:
            self.on_cad_status("generating")
            
        # Auto-create project if stuck in temp
        if self.project_manager.current_project == "temp":
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            print(f"[ADA DEBUG] [CAD] Auto-creating project: {new_project_name}")
            
            success, msg = self.project_manager.create_project(new_project_name)
            if success:
                self.project_manager.switch_project(new_project_name)
                # Notify User (Optional, or rely on update)
                try:
                    await self.session.send(input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.", end_of_turn=False)
                    if self.on_project_update:
                         self.on_project_update(new_project_name)
                except Exception as e:
                    print(f"[ADA DEBUG] [ERR] Failed to notify auto-project: {e}")

        # Get project cad folder path
        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        
        # Call the secondary agent with project path
        cad_data = await self.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        
        if cad_data:
            print(f"[ADA DEBUG] [OK] CadAgent returned data successfully.")
            print(f"[ADA DEBUG] [INFO] Data Check: {len(cad_data.get('vertices', []))} vertices, {len(cad_data.get('edges', []))} edges.")
            
            if self.on_cad_data:
                print(f"[ADA DEBUG] [SEND] Dispatching data to frontend callback...")
                self.on_cad_data(cad_data)
                print(f"[ADA DEBUG] [SENT] Dispatch complete.")
            
            # Save to Project
            if 'file_path' in cad_data:
                self.project_manager.save_cad_artifact(cad_data['file_path'], prompt)
            else:
                 # Fallback (legacy support)
                 self.project_manager.save_cad_artifact("output.stl", prompt)

            # Notify the model that the task is done - this triggers speech about completion
            completion_msg = "System Notification: CAD generation is complete! The 3D model is now displayed for the user. Let them know it's ready."
            try:
                await self.session.send(input=completion_msg, end_of_turn=True)
                print(f"[ADA DEBUG] [NOTE] Sent completion notification to model.")
            except Exception as e:
                 print(f"[ADA DEBUG] [ERR] Failed to send completion notification: {e}")

        else:
            print(f"[ADA DEBUG] [ERR] CadAgent returned None.")
            # Optionally notify failure
            try:
                await self.session.send(input="System Notification: CAD generation failed.", end_of_turn=True)
            except Exception:
                pass



    async def handle_write_file(self, path, content):
        print(f"[ADA DEBUG] [FS] Writing file: '{path}'")
        
        # Auto-create project if stuck in temp
        if self.project_manager.current_project == "temp":
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            print(f"[ADA DEBUG] [FS] Auto-creating project: {new_project_name}")
            
            success, msg = self.project_manager.create_project(new_project_name)
            if success:
                self.project_manager.switch_project(new_project_name)
                # Notify User
                try:
                    await self.session.send(input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.", end_of_turn=False)
                    if self.on_project_update:
                         self.on_project_update(new_project_name)
                except Exception as e:
                    print(f"[ADA DEBUG] [ERR] Failed to notify auto-project: {e}")
        
        # Force path to be relative to current project
        # If absolute path is provided, we try to strip it or just ignore it and use basename
        filename = os.path.basename(path)
        
        # If path contained subdirectories (e.g. "backend/server.py"), preserving that structure might be desired IF it's within the project.
        # But for safety, and per user request to "always create the file in the project", 
        # we will root it in the current project path.
        
        current_project_path = self.project_manager.get_current_project_path()
        final_path = current_project_path / filename # Simple flat structure for now, or allow relative?
        
        # If the user specifically wanted a subfolder, they might have provided "sub/file.txt".
        # Let's support relative paths if they don't start with /
        if not os.path.isabs(path):
             final_path = current_project_path / path
        
        print(f"[ADA DEBUG] [FS] Resolved path: '{final_path}'")

        try:
            # Ensure parent exists
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(content)
            result = f"File '{final_path.name}' written successfully to project '{self.project_manager.current_project}'."
        except Exception as e:
            result = f"Failed to write file '{path}': {str(e)}"

        print(f"[ADA DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[ADA DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_read_directory(self, path):
        print(f"[ADA DEBUG] [FS] Reading directory: '{path}'")
        try:
            if not os.path.exists(path):
                result = f"Directory '{path}' does not exist."
            else:
                items = os.listdir(path)
                result = f"Contents of '{path}': {', '.join(items)}"
        except Exception as e:
            result = f"Failed to read directory '{path}': {str(e)}"

        print(f"[ADA DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[ADA DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_read_file(self, path):
        print(f"[ADA DEBUG] [FS] Reading file: '{path}'")
        try:
            if not os.path.exists(path):
                result = f"File '{path}' does not exist."
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                result = f"Content of '{path}':\n{content}"
        except Exception as e:
            result = f"Failed to read file '{path}': {str(e)}"

        print(f"[ADA DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[ADA DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_web_agent_request(self, prompt):
        print(f"[ADA DEBUG] [WEB] Web Agent Task: '{prompt}'")
        
        async def update_frontend(image_b64, log_text):
            if self.on_web_data:
                 self.on_web_data({"image": image_b64, "log": log_text})
                 
        # Run the web agent and wait for it to return
        result = await self.web_agent.run_task(prompt, update_callback=update_frontend)
        print(f"[ADA DEBUG] [WEB] Web Agent Task Returned: {result}")
        
        # Send the final result back to the main model
        try:
             await self.session.send(input=f"System Notification: Web Agent has finished.\nResult: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[ADA DEBUG] [ERR] Failed to send web agent result to model: {e}")

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        try:
            while True:
                turn = self.session.receive()
                async for response in turn:
                    # 1. Handle Audio Data
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        # NOTE: 'continue' removed here to allow processing transcription/tools in same packet

                    # 2. Handle Transcription (User & Model)
                    if response.server_content:
                        if response.server_content.input_transcription:
                            transcript = response.server_content.input_transcription.text
                            if transcript:
                                # Skip if this is an exact duplicate event
                                if transcript != self._last_input_transcription:
                                    # Calculate delta (Gemini may send cumulative or chunk-based text)
                                    delta = transcript
                                    if transcript.startswith(self._last_input_transcription):
                                        delta = transcript[len(self._last_input_transcription):]
                                    self._last_input_transcription = transcript
                                    
                                    # Only send if there's new text
                                    if delta:
                                        # User is speaking, so interrupt model playback!
                                        self.clear_audio_queue()

                                        # Send to frontend (Streaming)
                                        if self.on_transcription:
                                             self.on_transcription({"sender": "User", "text": delta})
                                        
                                        # Buffer for Logging
                                        if self.chat_buffer["sender"] != "User":
                                            # Flush previous if exists
                                            if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                                self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                            # Start new
                                            self.chat_buffer = {"sender": "User", "text": delta}
                                        else:
                                            # Append
                                            self.chat_buffer["text"] += delta
                        
                        if response.server_content.output_transcription:
                            transcript = response.server_content.output_transcription.text
                            if transcript:
                                # Skip if this is an exact duplicate event
                                if transcript != self._last_output_transcription:
                                    # Calculate delta (Gemini may send cumulative or chunk-based text)
                                    delta = transcript
                                    if transcript.startswith(self._last_output_transcription):
                                        delta = transcript[len(self._last_output_transcription):]
                                    self._last_output_transcription = transcript
                                    
                                    # Only send if there's new text
                                    if delta:
                                        # Send to frontend (Streaming)
                                        if self.on_transcription:
                                             self.on_transcription({"sender": "ADA", "text": delta})
                                        
                                        # Buffer for Logging
                                        if self.chat_buffer["sender"] != "ADA":
                                            # Flush previous
                                            if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                                self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                            # Start new
                                            self.chat_buffer = {"sender": "ADA", "text": delta}
                                        else:
                                            # Append
                                            self.chat_buffer["text"] += delta
                        
                        # Flush buffer on turn completion if needed, 
                        # but usually better to wait for sender switch or explicit end.
                        # We can also check turn_complete signal if available in response.server_content.model_turn etc

                    # 3. Handle Tool Calls
                    if response.tool_call:
                        print("The tool was called")
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            if fc.name in ["generate_cad", "run_web_agent", "write_file", "read_directory", "read_file", "create_project", "switch_project", "list_projects", "list_smart_devices", "control_light", "discover_printers", "print_stl", "get_print_status", "iterate_cad", "ha_list_entities", "ha_control", "ha_get_state", "set_reminder", "list_reminders", "cancel_reminder", "show_camera"]:
                                prompt = fc.args.get("prompt", "") # Prompt is not present for all tools
                                
                                # Check Permissions (Default to True if not set)
                                confirmation_required = self.permissions.get(fc.name, True)
                                
                                if not confirmation_required:
                                    print(f"[ADA DEBUG] [TOOL] Permission check: '{fc.name}' -> AUTO-ALLOW")
                                    # Skip confirmation block and jump to execution
                                    pass
                                else:
                                    # Confirmation Logic
                                    if self.on_tool_confirmation:
                                        import uuid
                                        request_id = str(uuid.uuid4())
                                    print(f"[ADA DEBUG] [STOP] Requesting confirmation for '{fc.name}' (ID: {request_id})")
                                    
                                    future = asyncio.Future()
                                    self._pending_confirmations[request_id] = future
                                    
                                    self.on_tool_confirmation({
                                        "id": request_id, 
                                        "tool": fc.name, 
                                        "args": fc.args
                                    })
                                    
                                    try:
                                        # Wait for user response
                                        confirmed = await future

                                    finally:
                                        self._pending_confirmations.pop(request_id, None)

                                    print(f"[ADA DEBUG] [CONFIRM] Request {request_id} resolved. Confirmed: {confirmed}")

                                    if not confirmed:
                                        print(f"[ADA DEBUG] [DENY] Tool call '{fc.name}' denied by user.")
                                        function_response = types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={
                                                "result": "User denied the request to use this tool.",
                                            }
                                        )
                                        function_responses.append(function_response)
                                        continue

                                    if not confirmed:
                                        print(f"[ADA DEBUG] [DENY] Tool call '{fc.name}' denied by user.")
                                        function_response = types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={
                                                "result": "User denied the request to use this tool.",
                                            }
                                        )
                                        function_responses.append(function_response)
                                        continue

                                # If confirmed (or no callback configured, or auto-allowed), proceed
                                if fc.name == "generate_cad":
                                    print(f"\n[ADA DEBUG] --------------------------------------------------")
                                    print(f"[ADA DEBUG] [TOOL] Tool Call Detected: 'generate_cad'")
                                    print(f"[ADA DEBUG] [IN] Arguments: prompt='{prompt}'")
                                    
                                    asyncio.create_task(self.handle_cad_request(prompt))
                                    # No function response needed - model already acknowledged when user asked
                                
                                elif fc.name == "run_web_agent":
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'run_web_agent' with prompt='{prompt}'")
                                    asyncio.create_task(self.handle_web_agent_request(prompt))
                                    
                                    result_text = "Web Navigation started. Do not reply to this message."
                                    function_response = types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={
                                            "result": result_text,
                                        }
                                    )
                                    print(f"[ADA DEBUG] [RESPONSE] Sending function response: {function_response}")
                                    function_responses.append(function_response)



                                elif fc.name == "write_file":
                                    path = fc.args["path"]
                                    content = fc.args["content"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'write_file' path='{path}'")
                                    asyncio.create_task(self.handle_write_file(path, content))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Writing file..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "read_directory":
                                    path = fc.args["path"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'read_directory' path='{path}'")
                                    asyncio.create_task(self.handle_read_directory(path))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Reading directory..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "read_file":
                                    path = fc.args["path"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'read_file' path='{path}'")
                                    asyncio.create_task(self.handle_read_file(path))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Reading file..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "create_project":
                                    name = fc.args["name"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'create_project' name='{name}'")
                                    success, msg = self.project_manager.create_project(name)
                                    if success:
                                        # Auto-switch to the newly created project
                                        self.project_manager.switch_project(name)
                                        msg += f" Switched to '{name}'."
                                        if self.on_project_update:
                                            self.on_project_update(name)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "switch_project":
                                    name = fc.args["name"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'switch_project' name='{name}'")
                                    success, msg = self.project_manager.switch_project(name)
                                    if success:
                                        if self.on_project_update:
                                            self.on_project_update(name)
                                        # Gather project context and send to AI (silently, no response expected)
                                        context = self.project_manager.get_project_context()
                                        print(f"[ADA DEBUG] [PROJECT] Sending project context to AI ({len(context)} chars)")
                                        try:
                                            await self.session.send(input=f"System Notification: {msg}\n\n{context}", end_of_turn=False)
                                        except Exception as e:
                                            print(f"[ADA DEBUG] [ERR] Failed to send project context: {e}")
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": msg}
                                    )
                                    function_responses.append(function_response)
                                
                                elif fc.name == "list_projects":
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'list_projects'")
                                    projects = self.project_manager.list_projects()
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": f"Available projects: {', '.join(projects)}"}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "list_smart_devices":
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'list_smart_devices'")
                                    # Use cached devices directly for speed
                                    # devices_dict is {ip: SmartDevice}
                                    
                                    dev_summaries = []
                                    frontend_list = []
                                    
                                    for ip, d in self.kasa_agent.devices.items():
                                        dev_type = "unknown"
                                        if d.is_bulb: dev_type = "bulb"
                                        elif d.is_plug: dev_type = "plug"
                                        elif d.is_strip: dev_type = "strip"
                                        elif d.is_dimmer: dev_type = "dimmer"
                                        
                                        # Format for Model
                                        info = f"{d.alias} (IP: {ip}, Type: {dev_type})"
                                        if d.is_on:
                                            info += " [ON]"
                                        else:
                                            info += " [OFF]"
                                        dev_summaries.append(info)
                                        
                                        # Format for Frontend
                                        frontend_list.append({
                                            "ip": ip,
                                            "alias": d.alias,
                                            "model": d.model,
                                            "type": dev_type,
                                            "is_on": d.is_on,
                                            "brightness": d.brightness if d.is_bulb or d.is_dimmer else None,
                                            "hsv": d.hsv if d.is_bulb and d.is_color else None,
                                            "has_color": d.is_color if d.is_bulb else False,
                                            "has_brightness": d.is_dimmable if d.is_bulb or d.is_dimmer else False
                                        })
                                    
                                    result_str = "No devices found in cache."
                                    if dev_summaries:
                                        result_str = "Found Devices (Cached):\n" + "\n".join(dev_summaries)
                                    
                                    # Trigger frontend update
                                    if self.on_device_update:
                                        self.on_device_update(frontend_list)

                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "control_light":
                                    target = fc.args["target"]
                                    action = fc.args["action"]
                                    brightness = fc.args.get("brightness")
                                    color = fc.args.get("color")
                                    
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'control_light' Target='{target}' Action='{action}'")
                                    
                                    result_msg = f"Action '{action}' on '{target}' failed."
                                    success = False
                                    
                                    if action == "turn_on":
                                        success = await self.kasa_agent.turn_on(target)
                                        if success:
                                            result_msg = f"Turned ON '{target}'."
                                    elif action == "turn_off":
                                        success = await self.kasa_agent.turn_off(target)
                                        if success:
                                            result_msg = f"Turned OFF '{target}'."
                                    elif action == "set":
                                        success = True
                                        result_msg = f"Updated '{target}':"
                                    
                                    # Apply extra attributes if 'set' or if we just turned it on and want to set them too
                                    if success or action == "set":
                                        if brightness is not None:
                                            sb = await self.kasa_agent.set_brightness(target, brightness)
                                            if sb:
                                                result_msg += f" Set brightness to {brightness}."
                                        if color is not None:
                                            sc = await self.kasa_agent.set_color(target, color)
                                            if sc:
                                                result_msg += f" Set color to {color}."

                                    # Notify Frontend of State Change
                                    if success:
                                        # We don't need full discovery, just refresh known state or push update
                                        # But for simplicity, let's get the standard list representation
                                        # KasaAgent updates its internal state on control, so we can rebuild the list
                                        
                                        # Quick rebuild of list from internal dict
                                        updated_list = []
                                        for ip, dev in self.kasa_agent.devices.items():
                                            # We need to ensure we have the correct dict structure expected by frontend
                                            # We duplicate logic from KasaAgent.discover_devices a bit, but that's okay for now or we can add a helper
                                            # Ideally KasaAgent has a 'get_devices_list()' method.
                                            # Use the cached objects in self.kasa_agent.devices
                                            
                                            dev_type = "unknown"
                                            if dev.is_bulb: dev_type = "bulb"
                                            elif dev.is_plug: dev_type = "plug"
                                            elif dev.is_strip: dev_type = "strip"
                                            elif dev.is_dimmer: dev_type = "dimmer"

                                            d_info = {
                                                "ip": ip,
                                                "alias": dev.alias,
                                                "model": dev.model,
                                                "type": dev_type,
                                                "is_on": dev.is_on,
                                                "brightness": dev.brightness if dev.is_bulb or dev.is_dimmer else None,
                                                "hsv": dev.hsv if dev.is_bulb and dev.is_color else None,
                                                "has_color": dev.is_color if dev.is_bulb else False,
                                                "has_brightness": dev.is_dimmable if dev.is_bulb or dev.is_dimmer else False
                                            }
                                            updated_list.append(d_info)
                                            
                                        if self.on_device_update:
                                            self.on_device_update(updated_list)
                                    else:
                                        # Report Error
                                        if self.on_error:
                                            self.on_error(result_msg)

                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "discover_printers":
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'discover_printers'")
                                    printers = await self.printer_agent.discover_printers()
                                    # Format for model
                                    if printers:
                                        printer_list = []
                                        for p in printers:
                                            printer_list.append(f"{p['name']} ({p['host']}:{p['port']}, type: {p['printer_type']})")
                                        result_str = "Found Printers:\n" + "\n".join(printer_list)
                                    else:
                                        result_str = "No printers found on network. Ensure printers are on and running OctoPrint/Moonraker."
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "print_stl":
                                    stl_path = fc.args["stl_path"]
                                    printer = fc.args["printer"]
                                    profile = fc.args.get("profile")
                                    
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'print_stl' STL='{stl_path}' Printer='{printer}'")
                                    
                                    # Resolve 'current' to project STL
                                    if stl_path.lower() == "current":
                                        stl_path = "output.stl" # Let printer agent resolve it in root_path

                                    # Get current project path
                                    project_path = str(self.project_manager.get_current_project_path())
                                    
                                    result = await self.printer_agent.print_stl(
                                        stl_path, 
                                        printer, 
                                        profile, 
                                        root_path=project_path
                                    )
                                    result_str = result.get("message", "Unknown result")
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "get_print_status":
                                    printer = fc.args["printer"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'get_print_status' Printer='{printer}'")
                                    
                                    status = await self.printer_agent.get_print_status(printer)
                                    if status:
                                        result_str = f"Printer: {status.printer}\n"
                                        result_str += f"State: {status.state}\n"
                                        result_str += f"Progress: {status.progress_percent:.1f}%\n"
                                        if status.time_remaining:
                                            result_str += f"Time Remaining: {status.time_remaining}\n"
                                        if status.time_elapsed:
                                            result_str += f"Time Elapsed: {status.time_elapsed}\n"
                                        if status.filename:
                                            result_str += f"File: {status.filename}\n"
                                        if status.temperatures:
                                            temps = status.temperatures
                                            if "hotend" in temps:
                                                result_str += f"Hotend: {temps['hotend']['current']:.0f}°C / {temps['hotend']['target']:.0f}°C\n"
                                            if "bed" in temps:
                                                result_str += f"Bed: {temps['bed']['current']:.0f}°C / {temps['bed']['target']:.0f}°C"
                                    else:
                                        result_str = f"Could not get status for printer '{printer}'. Ensure it is discovered first."
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "iterate_cad":
                                    prompt = fc.args["prompt"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'iterate_cad' Prompt='{prompt}'")
                                    
                                    # Emit status
                                    if self.on_cad_status:
                                        self.on_cad_status("generating")
                                    
                                    # Get project cad folder path
                                    cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
                                    
                                    # Call CadAgent to iterate on the design
                                    cad_data = await self.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
                                    
                                    if cad_data:
                                        print(f"[ADA DEBUG] [OK] CadAgent iteration returned data successfully.")
                                        
                                        # Dispatch to frontend
                                        if self.on_cad_data:
                                            print(f"[ADA DEBUG] [SEND] Dispatching iterated CAD data to frontend...")
                                            self.on_cad_data(cad_data)
                                            print(f"[ADA DEBUG] [SENT] Dispatch complete.")
                                        
                                        # Save to Project
                                        self.project_manager.save_cad_artifact("output.stl", f"Iteration: {prompt}")
                                        
                                        result_str = f"Successfully iterated design: {prompt}. The updated 3D model is now displayed."
                                    else:
                                        print(f"[ADA DEBUG] [ERR] CadAgent iteration returned None.")
                                        result_str = f"Failed to iterate design with prompt: {prompt}"
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "ha_list_entities":
                                    domain = fc.args.get("domain")
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'ha_list_entities' domain={domain}")
                                    entities = await self.ha_agent.list_entities(domain=domain)
                                    if isinstance(entities, dict) and "error" in entities:
                                        result_str = entities["error"]
                                    elif isinstance(entities, dict) and "summary" in entities:
                                        lines = [f"  {d}: {c} entities" for d, c in sorted(entities["summary"].items())]
                                        result_str = f"Domain summary (call again with a specific domain to see entities):\n" + "\n".join(lines)
                                    else:
                                        lines = [f"- {e['friendly_name']} ({e['entity_id']}): {e['state']}" for e in entities]
                                        result_str = f"Found {len(entities)} entities:\n" + "\n".join(lines)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "ha_get_state":
                                    target = fc.args["target"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'ha_get_state' target={target}")
                                    entity_id = self.ha_agent.resolve_entity(target) or target
                                    state = await self.ha_agent.get_entity_state(entity_id)
                                    if "error" in state:
                                        result_str = state["error"]
                                    else:
                                        attrs = state.get("attributes", {})
                                        attr_lines = [f"  {k}: {v}" for k, v in attrs.items() if k != "friendly_name"]
                                        result_str = f"{state['friendly_name']} ({entity_id}): {state['state']}\nAttributes:\n" + "\n".join(attr_lines[:20])
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "ha_control":
                                    target = fc.args["target"]
                                    action = fc.args["action"]
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'ha_control' target={target} action={action}")
                                    print(f"[ADA DEBUG] [HA] configured={self.ha_agent.configured}, url={self.ha_agent.base_url}")

                                    # Resolve entity
                                    if not self.ha_agent.entities:
                                        await self.ha_agent.get_states()
                                    entity_id = self.ha_agent.resolve_entity(target) or target
                                    print(f"[ADA DEBUG] [HA] Resolved '{target}' -> '{entity_id}'")

                                    kwargs = {}
                                    if fc.args.get("brightness") is not None:
                                        kwargs["brightness"] = int(fc.args["brightness"])
                                    if fc.args.get("color_name"):
                                        kwargs["color_name"] = fc.args["color_name"]
                                    if fc.args.get("temperature") is not None:
                                        kwargs["temperature"] = float(fc.args["temperature"])

                                    if action == "turn_on":
                                        result = await self.ha_agent.turn_on(entity_id, **kwargs)
                                    elif action == "turn_off":
                                        result = await self.ha_agent.turn_off(entity_id, **kwargs)
                                    elif action == "toggle":
                                        result = await self.ha_agent.toggle(entity_id)
                                    elif action == "open_cover":
                                        result = await self.ha_agent.open_cover(entity_id)
                                    elif action == "close_cover":
                                        result = await self.ha_agent.close_cover(entity_id)
                                    elif action == "set_cover_position":
                                        pos = int(fc.args.get("position", 50))
                                        result = await self.ha_agent.set_cover_position(entity_id, pos)
                                    else:
                                        result = {"error": f"Unknown action: {action}"}

                                    print(f"[ADA DEBUG] [HA] Result: {result}")
                                    if "error" in result:
                                        result_str = f"Failed: {result['error']}"
                                    else:
                                        result_str = f"Successfully executed {action} on {entity_id}."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "set_reminder":
                                    message = fc.args["message"]
                                    minutes = int(fc.args.get("minutes", 0))
                                    hours = int(fc.args.get("hours", 0))
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'set_reminder' msg='{message}' {hours}h {minutes}m")
                                    result = await self.reminder_agent.add_reminder(message, minutes=minutes, hours=hours)
                                    if "error" in result:
                                        result_str = result["error"]
                                    else:
                                        result_str = f"Reminder set: '{message}' in {result['delay']} (at {result['fire_at']})"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "list_reminders":
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'list_reminders'")
                                    reminders = self.reminder_agent.list_reminders()
                                    if not reminders:
                                        result_str = "No pending reminders."
                                    else:
                                        lines = [f"- #{r['id']}: '{r['message']}' at {r['fire_at']}" for r in reminders]
                                        result_str = f"{len(reminders)} pending reminders:\n" + "\n".join(lines)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "cancel_reminder":
                                    rid = int(fc.args["reminder_id"])
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'cancel_reminder' id={rid}")
                                    success = self.reminder_agent.cancel_reminder(rid)
                                    result_str = f"Reminder #{rid} cancelled." if success else f"Reminder #{rid} not found."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "show_camera":
                                    camera = fc.args.get("camera")
                                    print(f"[ADA DEBUG] [TOOL] Tool Call: 'show_camera' camera={camera}")

                                    if not self.frigate_url:
                                        result_str = "Frigate is not configured. Set FRIGATE_URL in .env"
                                    elif not camera:
                                        # List available cameras
                                        if self.frigate_cameras:
                                            result_str = f"Available cameras: {', '.join(self.frigate_cameras)}"
                                        else:
                                            result_str = "No cameras found. Check FRIGATE_URL."
                                    else:
                                        # Fuzzy match camera name
                                        matched = None
                                        camera_lower = camera.lower().replace("ü", "u").replace("ä", "a").replace("ö", "o").replace("ß", "ss")
                                        for cam in self.frigate_cameras:
                                            cam_lower = cam.lower()
                                            if cam_lower == camera_lower or cam_lower in camera_lower or camera_lower in cam_lower:
                                                matched = cam
                                                break

                                        if not matched:
                                            result_str = f"Camera '{camera}' not found. Available: {', '.join(self.frigate_cameras)}"
                                        else:
                                            snapshot_url = f"{self.frigate_url}/api/{matched}/latest.jpg"
                                            print(f"[ADA DEBUG] [CAMERA] Matched '{camera}' -> '{matched}', URL: {snapshot_url}")
                                            if self.on_web_data:
                                                self.on_web_data({
                                                    "type": "camera_feed",
                                                    "camera": matched,
                                                    "snapshot_url": snapshot_url,
                                                    "frigate_url": self.frigate_url,
                                                })
                                            result_str = f"Showing live feed for camera '{matched}'."

                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                        if function_responses:
                            await self.session.send_tool_response(function_responses=function_responses)

                # Turn/Response Loop Finished
                self.flush_chat()

                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
        except Exception as e:
            print(f"Error in receive_audio: {e}")
            traceback.print_exc()
            # CRITICAL: Re-raise to crash the TaskGroup and trigger outer loop reconnect
            raise e

    async def play_audio(self):
        """Forward audio from Gemini to the browser via callback."""
        while True:
            bytestream = await self.audio_in_queue.get()
            if self.on_audio_data:
                self.on_audio_data(bytestream)

    async def get_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0, cv2.CAP_AVFOUNDATION)
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break
            await asyncio.sleep(1.0)
            if self.out_queue:
                await self.out_queue.put(frame)
        cap.release()

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        image_bytes = image_io.read()
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}

    async def _get_screen(self):
        pass 
    async def get_screen(self):
         pass

    async def run(self, start_message=None):
        retry_delay = 1
        is_reconnect = False
        
        while not self.stop_event.is_set():
            try:
                print(f"[ADA DEBUG] [CONNECT] Connecting to Gemini Live API...")
                async with (
                    client.aio.live.connect(model=MODEL, config=build_config(self.system_prompt)) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session

                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=10)

                    # Pre-fetch Home Assistant entities
                    if self.ha_agent.configured:
                        try:
                            await self.ha_agent.get_states()
                            print(f"[ADA] Loaded {len(self.ha_agent.entities)} Home Assistant entities")
                        except Exception as e:
                            print(f"[ADA] Failed to fetch HA entities: {e}")

                    # Pre-fetch Frigate cameras
                    if self.frigate_url:
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as sess:
                                async with sess.get(f"{self.frigate_url}/api/config", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                                    if resp.status == 200:
                                        config = await resp.json()
                                        self.frigate_cameras = list(config.get("cameras", {}).keys())
                                        print(f"[ADA] Loaded {len(self.frigate_cameras)} Frigate cameras: {self.frigate_cameras}")
                        except Exception as e:
                            print(f"[ADA] Failed to fetch Frigate cameras: {e}")

                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    # tg.create_task(self._process_video_queue()) # Removed in favor of VAD

                    if self.video_mode == "camera":
                        tg.create_task(self.get_frames())
                    elif self.video_mode == "screen":
                        tg.create_task(self.get_screen())

                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())

                    # Handle Startup vs Reconnect Logic
                    if not is_reconnect:
                        if start_message:
                            print(f"[ADA DEBUG] [INFO] Sending start message: {start_message}")
                            await self.session.send(input=start_message, end_of_turn=True)
                        
                        # Sync Project State
                        if self.on_project_update and self.project_manager:
                            self.on_project_update(self.project_manager.current_project)
                    
                    else:
                        print(f"[ADA DEBUG] [RECONNECT] Connection restored.")
                        # Restore Context
                        print(f"[ADA DEBUG] [RECONNECT] Fetching recent chat history to restore context...")
                        history = self.project_manager.get_recent_chat_history(limit=10)
                        
                        context_msg = "System Notification: Connection was lost and just re-established. Here is the recent chat history to help you resume seamlessly:\n\n"
                        for entry in history:
                            sender = entry.get('sender', 'Unknown')
                            text = entry.get('text', '')
                            context_msg += f"[{sender}]: {text}\n"
                        
                        context_msg += "\nPlease acknowledge the reconnection to the user (e.g. 'I lost connection for a moment, but I'm back...') and resume what you were doing."
                        
                        print(f"[ADA DEBUG] [RECONNECT] Sending restoration context to model...")
                        await self.session.send(input=context_msg, end_of_turn=True)

                    # Reset retry delay on successful connection
                    retry_delay = 1
                    
                    # Wait until stop event, or until the session task group exits (which happens on error)
                    # Actually, the TaskGroup context manager will exit if any tasks fail/cancel.
                    # We need to keep this block alive.
                    # The original code just waited on stop_event, but that doesn't account for session death.
                    # We should rely on the TaskGroup raising an exception when subtasks fail (like receive_audio).
                    
                    # However, since receive_audio is a task in the group, if it crashes (connection closed), 
                    # the group will cancel others and exit. We catch that exit below.
                    
                    # We can await stop_event, but if the connection dies, receive_audio crashes -> group closes -> we exit `async with` -> restart loop.
                    # To ensure we don't block indefinitely if connection dies silently (unlikely with receive_audio), we just wait.
                    await self.stop_event.wait()

            except asyncio.CancelledError:
                print(f"[ADA DEBUG] [STOP] Main loop cancelled.")
                break
                
            except Exception as e:
                # This catches the ExceptionGroup from TaskGroup or direct exceptions
                print(f"[ADA DEBUG] [ERR] Connection Error: {e}")
                
                if self.stop_event.is_set():
                    break
                
                print(f"[ADA DEBUG] [RETRY] Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10) # Exponential backoff capped at 10s
                is_reconnect = True # Next loop will be a reconnect
                
            finally:
                pass

def get_input_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    devices = []
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            devices.append((i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    p.terminate()
    return devices

def get_output_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    devices = []
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
            devices.append((i, p.get_device_info_by_host_api_device_index(0, i).get('name')))
    p.terminate()
    return devices

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioLoop(video_mode=args.mode)
    asyncio.run(main.run())