import speech_recognition as sr
import pyaudio
import wave
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ttkthemes import ThemedTk
from PIL import Image, ImageTk
import threading
import os
import time
from langdetect import detect
from pydub import AudioSegment
from googletrans import Translator
from faster_whisper import WhisperModel
import requests
from urllib.parse import quote

# Global variables
is_recording = False
is_paused = False
transcribed_text = ""
translated_text = ""

# List of supported Indian languages
INDIAN_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "gu": "Gujarati",
    "mr": "Marathi",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
}

# Initialize Whisper model (load it once at startup)
try:
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    print("Whisper model loaded successfully.")
except Exception as e:
    print(f"Failed to load Whisper model: {e}")
    whisper_model = None

def record_audio(output_audio_file=None):
    global is_recording, is_paused
    if not output_audio_file:
        output_audio_file = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
    frames = []

    print("Recording started...")
    while is_recording:
        if not is_paused:
            data = stream.read(1024)
            frames.append(data)

    print("Recording finished.")
    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(output_audio_file, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b''.join(frames))

    return output_audio_file

def detect_language(text):
    try:
        lang = detect(text)
        return lang
    except:
        return "en"

def transcribe_audio(output_text_file=None, audio_file=None, progress_callback=None):
    global transcribed_text, whisper_model
    
    if not whisper_model:
        messagebox.showerror("Error", "Whisper model failed to load. Transcription unavailable.")
        return None
        
    if not output_text_file:
        output_text_file = f"transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    if not audio_file.endswith(".wav"):
        try:
            audio = AudioSegment.from_file(audio_file)
            audio_file = audio_file.replace(".mp3", ".wav")
            audio.export(audio_file, format="wav")
        except Exception as e:
            print(f"Error converting audio file: {e}")
            return None

    try:
        segments, info = whisper_model.transcribe(audio_file, beam_size=5)
        full_text = " ".join([segment.text for segment in segments])
        transcribed_text = f"{full_text}\n\n"
        
        with open(output_text_file, "a", encoding="utf-8") as file:
            file.write(transcribed_text)
            
        print(f"Transcribed text saved to {output_text_file}")
        return output_text_file
        
    except Exception as e:
        print(f"Transcription failed: {e}")
        return None

def translate_text(text, target_language, max_chunk_size=4500):
    """Improved translation function with chunking and fallback"""
    if not text or not text.strip():
        return ""
        
    # First try the official Google Translate API
    try:
        translator = Translator()
        if len(text) <= max_chunk_size:
            translated = translator.translate(text, dest=target_language)
            return translated.text
    except Exception as e:
        print(f"Google Translate API failed: {e}")
    
    # If text is long or API failed, use chunking with web method
    chunks = []
    current_chunk = ""
    
    sentences = text.split('. ')
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_chunk_size:
            current_chunk += sentence + '. '
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = sentence + '. '
            else:
                chunks.append(sentence[:max_chunk_size])
                current_chunk = sentence[max_chunk_size:] + '. '
    
    if current_chunk:
        chunks.append(current_chunk)

    translated_chunks = []
    
    for chunk in chunks:
        for attempt in range(3):
            try:
                # Try web translation method
                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_language}&dt=t&q={quote(chunk)}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    translated_chunks.append(response.json()[0][0][0])
                    break
            except Exception as e:
                print(f"Translation attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    return None
                time.sleep(2)
    
    return ' '.join(translated_chunks)

class AudioTranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Teacher's Class Transcriber")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        self.root.set_theme("arc")

        # Load icons
        self.record_icon = ImageTk.PhotoImage(Image.open("record_icon.png").resize((32, 32)))
        self.pause_icon = ImageTk.PhotoImage(Image.open("pause_icon.png").resize((32, 32)))
        self.stop_icon = ImageTk.PhotoImage(Image.open("stop_icon.png").resize((32, 32)))
        self.import_icon = ImageTk.PhotoImage(Image.open("import_icon.png").resize((32, 32)))
        self.translate_icon = ImageTk.PhotoImage(Image.open("translate_icon.png").resize((32, 32)))
        self.export_icon = ImageTk.PhotoImage(Image.open("export_icon.png").resize((32, 32)))
        self.clear_icon = ImageTk.PhotoImage(Image.open("play_icon.png").resize((32, 32)))

        # Main Frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # Title Label
        self.title_label = ttk.Label(
            self.main_frame,
            text="Speech to text Transcriber",
            font=("Helvetica", 24, "bold"),
            foreground="#2c3e50"
        )
        self.title_label.pack(pady=20)

        # Buttons Frame
        self.buttons_frame = ttk.Frame(self.main_frame)
        self.buttons_frame.pack(pady=10)

        # Action Buttons
        self.record_button = ttk.Button(
            self.buttons_frame,
            text="Start Recording",
            image=self.record_icon,
            compound="left",
            command=self.toggle_recording,
            style="Accent.TButton"
        )
        self.record_button.pack(side="left", padx=10)

        self.pause_button = ttk.Button(
            self.buttons_frame,
            text="Pause",
            image=self.pause_icon,
            compound="left",
            command=self.toggle_pause,
            state=tk.DISABLED,
            style="Accent.TButton"
        )
        self.pause_button.pack(side="left", padx=10)

        self.import_button = ttk.Button(
            self.buttons_frame,
            text="Import Audio",
            image=self.import_icon,
            compound="left",
            command=self.import_audio_file,
            style="Accent.TButton"
        )
        self.import_button.pack(side="left", padx=10)

        self.clear_button = ttk.Button(
            self.buttons_frame,
            text="Clear",
            image=self.clear_icon,
            compound="left",
            command=self.clear_text,
            style="Accent.TButton"
        )
        self.clear_button.pack(side="left", padx=10)

        # Transcription Frame
        self.transcription_frame = ttk.LabelFrame(
            self.main_frame,
            text="Transcription",
            padding=10,
            style="Card.TFrame"
        )
        self.transcription_frame.pack(pady=10, fill="both", expand=True)

        self.transcription_text = tk.Text(
            self.transcription_frame,
            wrap="word",
            height=10,
            font=("Helvetica", 12),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        self.transcription_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Translation Frame
        self.translation_frame = ttk.LabelFrame(
            self.main_frame,
            text="Translation",
            padding=10,
            style="Card.TFrame"
        )
        self.translation_frame.pack(pady=10, fill="both", expand=True)

        self.translation_text = tk.Text(
            self.translation_frame,
            wrap="word",
            height=10,
            font=("Helvetica", 12),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        self.translation_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Language Selection
        self.language_var = tk.StringVar(value="hi")
        self.language_label = ttk.Label(
            self.translation_frame,
            text="Translate to:",
            font=("Helvetica", 12),
            foreground="#2c3e50"
        )
        self.language_label.pack(side="left", padx=5)

        self.language_menu = ttk.Combobox(
            self.translation_frame,
            textvariable=self.language_var,
            values=list(INDIAN_LANGUAGES.keys()),
            state="readonly",
            font=("Helvetica", 12)
        )
        self.language_menu.pack(side="left", padx=5)

        self.translate_button = ttk.Button(
            self.translation_frame,
            text="Translate",
            image=self.translate_icon,
            compound="left",
            command=self.translate_text,
            style="Accent.TButton"
        )
        self.translate_button.pack(side="left", padx=10)

        # Export Frame
        self.export_frame = ttk.Frame(self.main_frame)
        self.export_frame.pack(pady=10)

        self.export_txt_button = ttk.Button(
            self.export_frame,
            text="Export to TXT",
            image=self.export_icon,
            compound="left",
            command=self.export_to_txt,
            style="Accent.TButton"
        )
        self.export_txt_button.pack(side="left", padx=10)

        # Status and Footer
        self.status_label = ttk.Label(
            self.main_frame,
            text="Status: Idle",
            font=("Helvetica", 14),
            foreground="#2c3e50"
        )
        self.status_label.pack(pady=10)

        self.footer_label = ttk.Label(
            self.main_frame,
            text="© 2023 Teacher's Class Transcriber",
            font=("Helvetica", 12),
            foreground="#7f8c8d"
        )
        self.footer_label.pack(side="bottom", pady=10)

    def toggle_recording(self):
        global is_recording, transcribed_text
        if not is_recording:
            is_recording = True
            self.record_button.config(text="Stop Recording", image=self.stop_icon)
            self.pause_button.config(state=tk.NORMAL)
            self.status_label.config(text="Status: Recording...")
            threading.Thread(target=self.record_and_transcribe).start()
        else:
            is_recording = False
            self.record_button.config(text="Start Recording", image=self.record_icon)
            self.pause_button.config(state=tk.DISABLED)
            self.status_label.config(text="Status: Idle")

    def toggle_pause(self):
        global is_paused
        if not is_paused:
            is_paused = True
            self.pause_button.config(text="Resume", image=self.record_icon)
            self.status_label.config(text="Status: Paused")
        else:
            is_paused = False
            self.pause_button.config(text="Pause", image=self.pause_icon)
            self.status_label.config(text="Status: Recording...")

    def record_and_transcribe(self):
        global transcribed_text
        audio_file = record_audio()
        if audio_file:
            self.show_progress_dialog()
            text_file = transcribe_audio(audio_file=audio_file, progress_callback=self.update_progress)
            if text_file:
                self.transcription_text.insert("end", transcribed_text)
            self.progress_dialog.destroy()

    def import_audio_file(self):
        global transcribed_text
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio Files", "*.wav *.mp3")]
        )
        if file_path:
            self.show_progress_dialog()
            threading.Thread(target=self.transcribe_imported_audio, args=(file_path,)).start()

    def transcribe_imported_audio(self, file_path):
        global transcribed_text
        text_file = transcribe_audio(audio_file=file_path, progress_callback=self.update_progress)
        if text_file:
            self.transcription_text.insert("end", transcribed_text)
        self.progress_dialog.destroy()

    def show_progress_dialog(self):
        self.progress_dialog = tk.Toplevel(self.root)
        self.progress_dialog.title("Transcription Progress")
        self.progress_dialog.geometry("300x100")
        self.progress_dialog.resizable(False, False)

        self.progress_label = ttk.Label(self.progress_dialog, text="Transcribing...", font=("Helvetica", 12))
        self.progress_label.pack(pady=10)

        self.progress_bar = ttk.Progressbar(self.progress_dialog, orient="horizontal", length=250, mode="determinate")
        self.progress_bar.pack(pady=10)

    def update_progress(self, progress):
        self.progress_bar["value"] = progress
        self.progress_dialog.update_idletasks()

    def translate_text(self):
        global transcribed_text, translated_text
        target_language = self.language_var.get()
        
        if not transcribed_text or not transcribed_text.strip():
            messagebox.showwarning("No Text", "No transcribed text available for translation.")
            return
            
        self.status_label.config(text="Status: Translating...")
        self.root.update()
        
        try:
            # Show translation progress dialog
            self.show_translation_progress(len(transcribed_text))
            
            # Run translation in separate thread
            threading.Thread(
                target=self._perform_translation,
                args=(transcribed_text, target_language)
            ).start()
            
        except Exception as e:
            self.status_label.config(text="Status: Translation Failed")
            messagebox.showerror("Error", f"Translation initialization failed: {str(e)}")

    def _perform_translation(self, text, target_language):
        try:
            translated_text = translate_text(text, target_language)
            self.root.after(0, self._update_translation_result, translated_text)
        except Exception as e:
            self.root.after(0, self._translation_failed, str(e))
        finally:
            self.root.after(0, self.hide_translation_progress)

    def _update_translation_result(self, result):
        if result:
            self.translation_text.delete(1.0, tk.END)
            self.translation_text.insert(tk.END, result)
            self.status_label.config(text="Status: Translation Complete")
        else:
            self.status_label.config(text="Status: Translation Failed")
            messagebox.showerror("Error", "Translation failed after multiple attempts")

    def _translation_failed(self, error_msg):
        self.status_label.config(text="Status: Translation Failed")
        messagebox.showerror("Error", f"Translation failed: {error_msg}")

    def show_translation_progress(self, text_length):
        self.translation_progress_dialog = tk.Toplevel(self.root)
        self.translation_progress_dialog.title("Translating...")
        self.translation_progress_dialog.geometry("300x100")
        self.translation_progress_dialog.resizable(False, False)
        
        ttk.Label(self.translation_progress_dialog, 
                 text=f"Translating {text_length} characters...").pack()
        
        self.translation_progress = ttk.Progressbar(
            self.translation_progress_dialog, 
            orient="horizontal",
            length=300,
            mode="indeterminate"
        )
        self.translation_progress.pack()
        self.translation_progress.start()

    def hide_translation_progress(self):
        if hasattr(self, 'translation_progress_dialog'):
            self.translation_progress_dialog.destroy()

    def export_to_txt(self):
        global transcribed_text, translated_text
        if transcribed_text or translated_text:
            txt_file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
            if txt_file:
                with open(txt_file, "w", encoding="utf-8") as file:
                    file.write(f"Transcribed Text:\n{transcribed_text}\n\nTranslated Text:\n{translated_text}")
                messagebox.showinfo("Export Successful", f"Transcription and translation exported to {txt_file}")

    def clear_text(self):
        global transcribed_text, translated_text
        self.transcription_text.delete(1.0, tk.END)
        self.translation_text.delete(1.0, tk.END)
        transcribed_text = ""
        translated_text = ""
        messagebox.showinfo("Cleared", "Text areas have been cleared.")

if __name__ == "__main__":
    root = ThemedTk(theme="arc")
    app = AudioTranscriberApp(root)
    root.mainloop()